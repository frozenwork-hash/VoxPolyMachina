"""Generate one WAV per style for the phrase 'Ave Drago Nihilus'.

Usage:
    python scripts/gen_styles.py [--out-dir DIR] [--text TEXT]

Output files: Ave_<style>.wav in the output directory.
Default output directory: TestWav/ next to the project root.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from voxpolymachina.audio import audio_encode
from voxpolymachina.audio.styles import STYLES

DEFAULT_TEXT = "Ave Drago Nihilus"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default="TestWav",
        help="Directory for generated WAV files (default: TestWav)",
    )
    parser.add_argument(
        "--text",
        default=DEFAULT_TEXT,
        help=f"Text to encode (default: {DEFAULT_TEXT!r})",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for name in sorted(STYLES):
        path = out_dir / f"Ave_{name}.wav"
        try:
            audio_encode(args.text, path, style=name, config=None)
            size = path.stat().st_size
            print(f"OK   {name:14s} {path}  ({size} bytes)")
        except Exception as exc:
            failures += 1
            print(f"FAIL {name:14s} {exc}", file=sys.stderr)

    if failures:
        print(f"\n{failures} style(s) failed.", file=sys.stderr)
        return 1
    print(f"\nWrote {len(STYLES)} files to {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())