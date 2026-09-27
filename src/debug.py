from voxpolymachina._sentinel import _resolve_config
from voxpolymachina.audio.codec import _build_fsk, _normalize_peak
from voxpolymachina.audio.preamble import (
    find_preamble, find_preamble_debug, preamble_params_from_fsk,
)
from voxpolymachina.audio.wav import read_wav
import json

path = r"C:\Users\Frozen\AppData\Local\Temp\vpm_v3.wav"
cfg = _resolve_config({"audio": {"frequencies": [800.0, 2500.0]}})
samples, sr = read_wav(path)
samples = _normalize_peak(samples)
fsk = _build_fsk(cfg, 2, sr, 50.0)
pp = preamble_params_from_fsk(fsk, 6, "trill")

print("sample_rate:", sr)
print("len(samples):", len(samples))
print("n_per:", pp.symbol_samples)
print("silence_samples:", pp.silence_samples)
print("total_preamble:", pp.total_samples)
print("expected payload start:", pp.total_samples)
print("available if start=total:", len(samples) - pp.total_samples)

found = find_preamble(samples, pp)
print("find_preamble ->", found)
if found is not None:
    print("available after start:", len(samples) - found)
    print("max_symbols:", (len(samples) - found) // pp.symbol_samples)

print("--- debug json ---")
print(json.dumps(find_preamble_debug(samples, pp), indent=2))