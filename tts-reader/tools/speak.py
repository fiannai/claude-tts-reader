#!/usr/bin/env python3
"""
Streaming TTS tool - reads text aloud with minimal latency.

Generates all sentence audio as fast as possible. Starts playback once
batch_start_percent of sentences are ready. Plays everything available
as a single concatenated WAV, then grabs whatever accumulated during
playback for the next WAV. Repeats until done.

Config: tts-config.json (next to this script, hot-reloaded on change)
User voice override: ~/.tts_voice
Stop reading: create ~/.tts_stop file (or run stop-tts.bat)
"""
import json
import os
import random
import re
import struct
import subprocess
import sys
import tempfile
import threading
import time
from queue import Queue, Empty
from typing import List

STOP_SENTINEL = os.path.expanduser("~/.tts_stop")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "tts-config.json")

try:
    import requests
except ImportError:
    print("Error: requests library not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Config with hot-reload
# ---------------------------------------------------------------------------

DEFAULTS = {
    "api_url": "http://waternoose:8765",
    "tts_path": "/v1/tts/synthesize",
    "api_key_file": "~/.tts_api_key",
    "default_voice": "af_heart",
    "max_queue_size": 20,
    "request_timeout": 30,
    "sentence_pause_min_ms": 80,
    "sentence_pause_max_ms": 120,
    "batch_start_percent": 25,
}


class Config:
    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._mtime: float = 0
        self._data: dict = dict(DEFAULTS)
        self._reload()

    def _reload(self) -> None:
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            return
        if mtime == self._mtime:
            return
        try:
            with open(self._path, 'r') as f:
                user = json.load(f)
            with self._lock:
                self._data = {**DEFAULTS, **user}
                self._mtime = mtime
        except (json.JSONDecodeError, IOError):
            pass

    def get(self, key: str):
        self._reload()
        with self._lock:
            return self._data.get(key, DEFAULTS.get(key))


config = Config(CONFIG_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_voice() -> str:
    voice_file = os.path.expanduser("~/.tts_voice")
    if os.path.exists(voice_file):
        try:
            with open(voice_file, 'r') as f:
                v = f.read().strip()
                if v:
                    return v
        except IOError:
            pass
    return config.get("default_voice")


def should_stop() -> bool:
    if os.path.exists(STOP_SENTINEL):
        try:
            os.remove(STOP_SENTINEL)
        except OSError:
            pass
        return True
    return False


def sanitize_text(text: str) -> str:
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'```[\s\S]*?```', ' code block ', text)
    text = re.sub(r'`[^`]+`', ' ', text)
    text = re.sub(r'https?://\S+', ' ', text)
    text = re.sub(r'[#*_~`\[\]{}]', '', text)
    text = re.sub(r'\|', ' ', text)
    text = re.sub(r'-{3,}', ' ', text)
    text = re.sub(r'\n\n+', '. ', text)
    text = re.sub(r'\n', '. ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\.(\s*\.)+', '.', text)
    return text.strip()


def chunk_by_sentence(text: str) -> List[str]:
    text = sanitize_text(text)
    parts = re.split(r'(?<=[.!?])\s+', text)
    sentences = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) < 3 and not any(c.isalpha() for c in part):
            continue
        sentences.append(part)
    return sentences


def get_api_key() -> str:
    """Read the API key from the configured key file (never committed)."""
    key_file = os.path.expanduser(config.get("api_key_file"))
    try:
        with open(key_file, 'r') as f:
            return f.read().strip()
    except IOError:
        return ""


def generate_audio(text: str, voice: str) -> bytes:
    payload = {"text": text, "voice": voice}
    endpoint = config.get("api_url").rstrip('/') + config.get("tts_path")
    headers = {}
    api_key = get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(endpoint, json=payload, headers=headers,
                             timeout=config.get("request_timeout"))
    if response.status_code != 200:
        print(f"API Error: {response.text}", file=sys.stderr)
    response.raise_for_status()
    return response.content


def strip_wav_header(wav_data: bytes) -> tuple:
    if wav_data[:4] != b'RIFF':
        raise ValueError("Not a WAV file")
    pos = 12
    sr, ch, bits = 24000, 1, 16
    while pos < len(wav_data) - 8:
        chunk_id = wav_data[pos:pos + 4]
        chunk_size = struct.unpack_from('<I', wav_data, pos + 4)[0]
        if chunk_id == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', wav_data, pos + 8)
            ch, sr, bits = fmt[1], fmt[2], fmt[5]
        elif chunk_id == b'data':
            return wav_data[pos + 8:pos + 8 + chunk_size], sr, ch, bits
        pos += 8 + chunk_size
    raise ValueError("No data chunk in WAV")


def generate_silence(duration_ms: int, sample_rate: int, channels: int,
                     bits_per_sample: int) -> bytes:
    bytes_per_sample = bits_per_sample // 8
    num_samples = int(sample_rate * channels * duration_ms / 1000)
    return b'\x00' * (num_samples * bytes_per_sample)


def trim_trailing_silence(pcm: bytes, bits_per_sample: int,
                          threshold: int = 80) -> bytes:
    bytes_per_sample = bits_per_sample // 8
    fmt = '<h' if bits_per_sample == 16 else '<b'
    num_samples = len(pcm) // bytes_per_sample
    end = num_samples
    for i in range(num_samples - 1, -1, -1):
        offset = i * bytes_per_sample
        sample = struct.unpack_from(fmt, pcm, offset)[0]
        if abs(sample) > threshold:
            end = i + 1
            break
    else:
        end = min(num_samples, 100)
    end = min(end + 50, num_samples)
    return pcm[:end * bytes_per_sample]


def build_wav(pcm_data: bytes, sample_rate: int, channels: int,
              bits_per_sample: int) -> bytes:
    bytes_per_sample = bits_per_sample // 8
    byte_rate = sample_rate * channels * bytes_per_sample
    block_align = channels * bytes_per_sample
    data_size = len(pcm_data)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, channels, sample_rate,
        byte_rate, block_align, bits_per_sample,
        b'data', data_size,
    )
    return header + pcm_data


# ---------------------------------------------------------------------------
# Audio generation thread
# ---------------------------------------------------------------------------

def audio_generator(
    sentences: List[str], voice: str,
    pcm_queue: Queue, stop_event: threading.Event
) -> None:
    """Generate PCM for every sentence as fast as possible."""
    for i, sentence in enumerate(sentences):
        if stop_event.is_set():
            break
        try:
            wav_data = generate_audio(sentence, voice)
            pcm, sr, ch, bits = strip_wav_header(wav_data)
            pcm = trim_trailing_silence(pcm, bits)
            pcm_queue.put(("audio", pcm, sr, ch, bits))
        except Exception as e:
            print(f"Error generating sentence {i}: {e}", file=sys.stderr)
    pcm_queue.put(("DONE",))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Streaming TTS")
    parser.add_argument("text", nargs="?")
    parser.add_argument("--api-url", default=None)
    parser.add_argument("--voice", default=None)
    args = parser.parse_args()

    if args.api_url:
        DEFAULTS["api_url"] = args.api_url
    voice = args.voice or get_voice()

    if os.path.exists(STOP_SENTINEL):
        os.remove(STOP_SENTINEL)

    text = args.text if args.text else sys.stdin.read()
    if not text.strip():
        print("Error: No text provided", file=sys.stderr)
        return 1

    sentences = chunk_by_sentence(text)
    if not sentences:
        print("Error: No speakable text", file=sys.stderr)
        return 1

    total = len(sentences)
    start_pct = config.get("batch_start_percent")
    start_threshold = max(1, int(total * start_pct / 100))

    print(f"Reading {total} sentences (start after {start_threshold})...",
          file=sys.stderr)

    stop_event = threading.Event()
    pcm_queue = Queue(maxsize=config.get("max_queue_size"))
    temp_dir = tempfile.mkdtemp(prefix="tts_")

    gen_thread = threading.Thread(
        target=audio_generator,
        args=(sentences, voice, pcm_queue, stop_event),
        daemon=True,
    )
    gen_thread.start()

    # Collect PCM chunks as they arrive
    # Each entry: (pcm_bytes, sample_rate, channels, bits)
    ready_chunks = []
    generator_done = False
    sample_rate = channels = bits = None
    batch_num = 0

    def drain_queue():
        """Pull all immediately available items from the generator queue."""
        nonlocal generator_done, sample_rate, channels, bits
        while True:
            try:
                item = pcm_queue.get_nowait()
            except Empty:
                return
            if item[0] == "DONE":
                generator_done = True
                return
            _, pcm, sr, ch, b = item
            sample_rate = sr
            channels = ch
            bits = b
            ready_chunks.append(pcm)

    def wait_for_one():
        """Block until at least one new chunk arrives."""
        nonlocal generator_done, sample_rate, channels, bits
        try:
            item = pcm_queue.get(timeout=60)
        except Empty:
            generator_done = True
            return
        if item[0] == "DONE":
            generator_done = True
            return
        _, pcm, sr, ch, b = item
        sample_rate = sr
        channels = ch
        bits = b
        ready_chunks.append(pcm)

    def build_and_play(chunks: list) -> bool:
        """Concatenate PCM chunks with pauses, build WAV, play it.
        Returns False if stop was requested."""
        nonlocal batch_num
        if not chunks or not sample_rate:
            return True

        combined = bytearray()
        for i, pcm in enumerate(chunks):
            if i > 0:
                pause = random.randint(
                    config.get("sentence_pause_min_ms"),
                    config.get("sentence_pause_max_ms"),
                )
                combined.extend(
                    generate_silence(pause, sample_rate, channels, bits))
            combined.extend(pcm)

        wav = build_wav(bytes(combined), sample_rate, channels, bits)
        path = os.path.join(temp_dir, f"batch_{batch_num}.wav")
        with open(path, 'wb') as f:
            f.write(wav)
        batch_num += 1

        try:
            player = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                 "-i", path],
            )
            player.wait()
        except Exception as e:
            print(f"Playback error: {e}", file=sys.stderr)
        finally:
            if os.path.exists(path):
                os.remove(path)

        return not should_stop()

    try:
        # Phase 1: Wait for start_threshold sentences
        while len(ready_chunks) < start_threshold and not generator_done:
            if should_stop():
                stop_event.set()
                break
            wait_for_one()
            drain_queue()

        if stop_event.is_set():
            return 0

        # Phase 2: Play what we have, then loop
        while True:
            if should_stop():
                stop_event.set()
                break

            if not ready_chunks and generator_done:
                break

            if not ready_chunks:
                wait_for_one()
                drain_queue()
                continue

            # Grab all ready chunks, play them
            to_play = ready_chunks[:]
            ready_chunks.clear()

            if not build_and_play(to_play):
                stop_event.set()
                break

            # After playback, drain whatever accumulated
            drain_queue()

    finally:
        stop_event.set()
        gen_thread.join(timeout=5)
        for f in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, f))
            except Exception:
                pass
        try:
            os.rmdir(temp_dir)
        except Exception:
            pass

    print("Done.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
