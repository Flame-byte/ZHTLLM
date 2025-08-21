#!/usr/bin/env python3
"""
Record audio from microphone, resample to a target sample rate, and save to file.
Dependencies: sounddevice, soundfile, librosa, numpy
"""
import argparse
from pathlib import Path

import sounddevice as sd
import soundfile as sf
import numpy as np
import librosa


def record_audio(
    duration: float,
    output_path: str,
    target_sr: int = 16000,
    channels: int = 1,
    dtype: str = 'float32',
) -> None:
    """
    Record audio from the default microphone for a given duration (in seconds),
    resample to target_sr, and save to output_path.

    Args:
        duration: Recording duration in seconds.
        output_path: Path to write the output audio file (e.g. 'out.wav').
        target_sr: Target sample rate in Hz (default: 16000).
        channels: Number of channels (1=mono, 2=stereo).
        dtype: Data type for recording (e.g. 'float32', 'int16').
    """
    # Query default input device sample rate
    default_sr = int(sd.query_devices(None, 'input')['default_samplerate'])
    print(f"Recording at {default_sr} Hz for {duration} seconds...")

    # Record audio
    data = sd.rec(
        frames=int(duration * default_sr),
        samplerate=default_sr,
        channels=channels,
        dtype=dtype,
    )
    sd.wait()

    # Resample if needed
    if default_sr != target_sr:
        # For multi-channel, resample each channel individually
        if channels == 1:
            mono = data.flatten()
            res = librosa.resample(mono, orig_sr=default_sr, target_sr=target_sr)
            data = res.reshape(-1, 1)
        else:
            resampled = []
            for ch in range(channels):
                res_ch = librosa.resample(
                    data[:, ch], orig_sr=default_sr, target_sr=target_sr
                )
                resampled.append(res_ch)
            # stack channels back (n_frames, channels)
            data = np.stack(resampled, axis=1)

    # Ensure output directory exists
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    sf.write(str(out_path), data, samplerate=target_sr)
    print(f"Saved recorded audio to {out_path} (sr={target_sr})")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Record microphone audio, resample to target sample rate, and save to file."
    )
    parser.add_argument(
        '-d', '--duration', type=float, required=True,
        help='Recording duration in seconds.'
    )
    parser.add_argument(
        '-o', '--output', type=str, required=True,
        help='Path to save the recorded audio (e.g. output.wav).'
    )
    parser.add_argument(
        '-r', '--samplerate', type=int, default=16000,
        help='Target sample rate in Hz (default: 16000).'
    )
    parser.add_argument(
        '-c', '--channels', type=int, default=1,
        help='Number of channels (1=mono, 2=stereo).'
    )
    parser.add_argument(
        '--dtype', type=str, default='float32',
        help='Data type for recording (e.g. float32).'
    )
    args = parser.parse_args()

    record_audio(
        duration=args.duration,
        output_path=args.output,
        target_sr=args.samplerate,
        channels=args.channels,
        dtype=args.dtype,
    ) 