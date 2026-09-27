import os, tempfile
from voxpolymachina.audio import audio_encode, audio_decode, audio_info

path = os.path.join(tempfile.gettempdir(), "vpm_rt.wav")

cases = [
    ("", 4),
    ("A", 4),
    ("Hello, world", 4),
    ("Привет 🌍", 4),
    ("Hello, world", 2),
    ("Привет 🌍", 36),
    ("a\tb\nc", 8),
]

for text, abase in cases:
    audio_encode(text, path, audio_base=abase, config=None)
    back = audio_decode(path, audio_base=abase, config=None)
    status = "OK" if back == text else "FAIL"
    print(f"{status} base={abase:2d}  {text!r} -> {back!r}")

print(audio_info(path, config=None))