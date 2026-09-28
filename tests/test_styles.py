"""Smoke test: every style must encode and decode without errors."""
from __future__ import annotations

import pytest

from voxpolymachina.audio import audio_decode, audio_encode
from voxpolymachina.audio.styles import STYLES


@pytest.mark.parametrize("style_name", sorted(STYLES))
def test_style_encodes_and_decodes(tmp_path, style_name: str) -> None:
    style = STYLES[style_name]
    if not style.decodable:
        pytest.skip(f"style {style_name!r} is decorative only")
    path = tmp_path / f"Ave_{style_name}.wav"
    text = "Ave Drago Nihilus"
    audio_encode(text, path, style=style_name, config=None)
    back = audio_decode(path, style=style_name, config=None)
    assert back == text


@pytest.mark.parametrize("style_name", sorted(STYLES))
def test_style_writes_to_disk(tmp_path, style_name: str) -> None:
    path = tmp_path / f"out_{style_name}.wav"
    audio_encode("A", path, style=style_name, config=None)
    assert path.exists()
    assert path.stat().st_size > 44  # bigger than a WAV header