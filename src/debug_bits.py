"""Dump decoded bits from a real recording for visual inspection."""
import json
import sys

from voxpolymachina._sentinel import _resolve_config
from voxpolymachina.audio.codec import _build_fsk, _normalize_peak
from voxpolymachina.audio.preamble import (
    find_preamble, find_preamble_debug, preamble_params_from_fsk,
)
from voxpolymachina.audio.wav import read_wav
from voxpolymachina.audio.fsk import samples_to_symbols
from voxpolymachina.basecodec import base_to_bits

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Frozen\Documents\Audacity\rec_v3.wav"
freqs = [800.0, 2500.0]
audio_base = 2
symbol_ms = 50.0

cfg = _resolve_config({"audio": {"frequencies": freqs}})
samples, sr = read_wav(path)
samples = _normalize_peak(samples)
fsk = _build_fsk(cfg, audio_base, sr, symbol_ms)
pp = preamble_params_from_fsk(fsk, 6, "trill")

print("== preamble debug ==")
print(json.dumps(find_preamble_debug(samples, pp), indent=2))

found = find_preamble(samples, pp)
print("find_preamble ->", found)
if found is None:
    sys.exit(1)

n_per = fsk.symbol_samples
available = len(samples) - found
max_symbols = available // n_per
all_symbols = samples_to_symbols(
    samples[found : found + max_symbols * n_per],
    max_symbols,
    fsk,
)
print("max_symbols:", max_symbols)

# Decode first 224 symbols (expected payload size for HELLO in base 2)
N = 224
if max_symbols < N:
    print(f"warning: only {max_symbols} symbols available, need {N}")
    N = max_symbols

syms = all_symbols[:N]
combined = base_to_bits(syms, audio_base)
print("first 32 bits:", combined[:32])
print("expected     :", format(0x5650, "016b") + format(1, "04b") + format(0, "04b"))

# Compare bit-by-bit in the first 96 bits (header)
expected_header = (
    format(0x5650, "016b")  # magic
    + format(1, "04b")       # version
    + format(0, "04b")       # mode (codepoint21)
    + format(1, "04b")       # block_size
    + format(0, "01b")       # has_hash
    + format(0, "03b")       # reserved
)
print("--- bit comparison (first 32) ---")
print("got :", combined[:32])
print("want:", expected_header[:32])
print("diff:", "".join(
    "." if a == b else "X" for a, b in zip(combined[:32], expected_header[:32])
))

# Try to find 0x5650 anywhere in the bitstream — if found, it's a
# timing offset; if not, it's bit errors.
needle = format(0x5650, "016b")
for shift in range(0, 64):
    if combined[shift : shift + 16] == needle:
        print(f"magic found at bit shift {shift}")
        break
else:
    print("magic NOT found in first 64 bits — errors are not a pure shift")