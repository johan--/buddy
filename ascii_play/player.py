"""
ascii_play.player


Video decode + render loop.

Install audio dep:
pip install sounddevice soundfile
"""

import os
import sys
import time
import shutil
import signal
import threading
import tempfile
import subprocess

import numpy as np
import imageio_ffmpeg

from .ansi      import alt_screen, normal_screen, cursor_hide, cursor_show, \
                       clear_screen, reset, move_to
from .renderers import MODES, render_half

# ── audio ─────────────────────────────────────────────────────────────────────

def _has_audio_deps():
    try:
        import sounddevice, soundfile
        return True
    except ImportError:
        return False

def _extract_audio(filename, tmp_path):
    """Extract audio from video to a wav file using ffmpeg."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-y", "-i", filename, "-vn", "-acodec", "pcm_s16le",
         "-ar", "44100", "-ac", "2", tmp_path],
        capture_output=True
    )
    return result.returncode == 0

class AudioClock:
    """
    Plays audio in a background thread and exposes the current playback
    position as a precise timestamp. Video render loop uses this as master clock.
    """
    def __init__(self, wav_path):
        import soundfile as sf
        import sounddevice as sd

        self._data, self._sr = sf.read(wav_path, dtype="float32")
        self._pos     = 0           # current sample position
        self._lock    = threading.Lock()
        self._stream  = None
        self._started = threading.Event()
        self._done    = threading.Event()
        self._sd      = sd

    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            chunk = self._data[self._pos : self._pos + frames]
            if len(chunk) < frames:
                outdata[:len(chunk)] = chunk
                outdata[len(chunk):] = 0
                self._pos += len(chunk)
                self._done.set()
                raise self._sd.CallbackStop()
            else:
                outdata[:] = chunk
                self._pos += frames
        self._started.set()

    def start(self):
        self._stream = self._sd.OutputStream(
            samplerate=self._sr,
            channels=self._data.shape[1] if self._data.ndim > 1 else 1,
            callback=self._callback,
            dtype="float32",
        )
        self._stream.start()
        self._started.wait(timeout=2.0)

    @property
    def time(self):
        """Current playback position in seconds."""
        with self._lock:
            return self._pos / self._sr

    def is_done(self):
        return self._done.is_set()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()


# ── player ────────────────────────────────────────────────────────────────────

def play(
    filename : str,
    mode     : str   = "half",
    scale    : float = 1.0,
    loop     : bool  = False,
    info     : bool  = True,
    quality  : int   = 2,
    audio    : bool  = True,
) -> None:
    renderer = MODES.get(mode, render_half)

    interrupted = threading.Event()
    def _on_signal(sig, _frame):
        interrupted.set()
    signal.signal(signal.SIGINT,  _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    sys.stdout.write(alt_screen())
    sys.stdout.write(cursor_hide())
    sys.stdout.write(clear_screen())
    sys.stdout.flush()

    try:
        _loop(filename, renderer, mode, scale, loop, info, quality, audio, interrupted)
    finally:
        sys.stdout.write(reset())
        sys.stdout.write(normal_screen())
        sys.stdout.write(cursor_show())
        sys.stdout.flush()


def _loop(filename, renderer, mode, scale, loop, info, quality, audio, interrupted):
    use_audio = audio and _has_audio_deps()

    while True:
        # ── extract audio ──────────────────────────────────────────────────
        clock      = None
        tmp_wav    = None

        if use_audio:
            tmp_wav = tempfile.mktemp(suffix=".wav")
            if _extract_audio(filename, tmp_wav):
                try:
                    clock = AudioClock(tmp_wav)
                    clock.start()
                except Exception:
                    clock = None
            if clock is None and os.path.exists(tmp_wav):
                os.unlink(tmp_wav)

        # ── video decode ───────────────────────────────────────────────────
        video = imageio_ffmpeg.read_frames(filename)
        meta  = next(video)
        fps   = meta.get("fps", 24) or 24
        vw, vh = meta["size"]
        frame_size = (vh, vw, 3)
        spf   = 1.0 / fps

        frame_count = 0
        t_start     = time.perf_counter()

        try:
            for raw in video:
                if interrupted.is_set():
                    return

                frame = np.frombuffer(raw, dtype=np.uint8).reshape(frame_size)

                # ── audio-slaved sync ──────────────────────────────────────
                if clock is not None:
                    audio_time    = clock.time
                    expected_frame = int(audio_time * fps)
                    # drop frames if we're behind audio
                    if expected_frame > frame_count + 1:
                        frame_count = expected_frame
                        continue
                else:
                    # no audio — classic timer sync
                    target = t_start + frame_count * spf
                    slack  = target - time.perf_counter()
                    if slack > 0:
                        time.sleep(slack)

                # ── render ─────────────────────────────────────────────────
                term_cols, term_rows = shutil.get_terminal_size((80, 24))
                cols        = max(1, int(term_cols * scale))
                rows        = max(1, int(term_rows * scale))
                render_rows = max(1, rows - 1) if info else rows

                out = renderer(frame, cols, render_rows, quality)

                if info:
                    elapsed    = time.perf_counter() - t_start
                    actual_fps = frame_count / elapsed if elapsed > 0 else 0
                    audio_tag  = "audio" if clock else "no audio"
                    out += (
                        move_to(rows)
                        + "\033[48;2;18;18;18m\033[38;2;170;170;170m"
                        + f"  {os.path.basename(filename)}"
                        + f"  │  {mode}"
                        + f"  │  q{quality}"
                        + f"  │  {cols}×{render_rows}"
                        + f"  │  {actual_fps:.1f}/{fps:.0f} fps"
                        + f"  │  {audio_tag}"
                        + "\033[K"
                        + reset()
                    )

                sys.stdout.write(out)
                sys.stdout.flush()
                frame_count += 1

        finally:
            if clock:
                clock.stop()
            if tmp_wav and os.path.exists(tmp_wav):
                os.unlink(tmp_wav)

        if not loop:
            break