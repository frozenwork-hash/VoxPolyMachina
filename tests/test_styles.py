"""Smoke test: every style must encode and decode without errors."""
from __future__ import annotations

import pytest

from voxpolymachina.audio import audio_decode, audio_encode
from voxpolymachina.audio.styles import STYLES


@pytest.mark.parametrize("style_name", sorted(STYLES))
def test_style_encodes_and_decodes(tmp_path, style_name: str) -> None:
    """Round-trip with effects disabled.

    Effects can distort the signal enough that preamble detection
    fails; testing the codec cleanly means disabling them. Effects
    themselves are tested separately.
    """
    style = STYLES[style_name]
    if not style.decodable:
        pytest.skip(f"style {style_name!r} is decorative only")
    path = tmp_path / f"Ave_{style_name}.wav"
    text = "Ave Drago Nihilus"
    audio_encode(text, path, style=style_name, effects=[], config=None)
    back = audio_decode(path, style=style_name, effects=[], config=None)
    assert back == text


@pytest.mark.parametrize("style_name", sorted(STYLES))
def test_style_writes_to_disk(tmp_path, style_name: str) -> None:
    path = tmp_path / f"out_{style_name}.wav"
    audio_encode("A", path, style=style_name, config=None)
    assert path.exists()
    assert path.stat().st_size > 44


@pytest.mark.parametrize("style_name", sorted(STYLES))
def test_style_with_effects_writes_file(tmp_path, style_name: str) -> None:
    """With effects enabled, the file is written and non-empty.

    No decoding: some effects are destructive by design.
    """
    style = STYLES[style_name]
    if not style.effects:
        pytest.skip(f"style {style_name!r} has no effects")
    path = tmp_path / f"Ave_{style_name}_fx.wav"
    audio_encode("Ave Drago Nihilus", path, style=style_name, config=None)
    assert path.exists()
    assert path.stat().st_size > 44


def test_effects_change_signal() -> None:
    """A style with effects must produce different samples than without."""
    clean, sr = audio_encode(
        "test", inline=True, style="omnissiah", effects=[], config=None
    )
    colored, sr2 = audio_encode(
        "test", inline=True, style="omnissiah", config=None
    )
    assert sr == sr2
    assert len(clean) == len(colored)
    assert any(abs(a - b) > 1e-6 for a, b in zip(clean, colored))


def test_unknown_effect_rejected() -> None:
    from voxpolymachina.audio.effects import apply_effects

    with pytest.raises(ValueError, match="unknown effect"):
        apply_effects([0.1, 0.2, 0.3], 44100, ["not_a_real_effect"])

@pytest.mark.parametrize("style_name", sorted(STYLES))
def test_style_writes_to_disk(tmp_path, style_name: str) -> None:
    path = tmp_path / f"out_{style_name}.wav"
    audio_encode("A", path, style=style_name, config=None)
    assert path.exists()
    assert path.stat().st_size > 44  # bigger than a WAV header