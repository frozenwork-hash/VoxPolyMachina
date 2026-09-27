"""Round-trip tests for text <-> base N encoding."""
import pytest

from voxpolymachina import decode, encode


@pytest.mark.parametrize("base", [2, 3, 5, 8, 10, 16, 36])
@pytest.mark.parametrize(
    "text",
    [
        "",
        "A",
        "Hello, world",
        "Привет",
        "🌍",
        "Привет 🌍 123",
        "a\tb\nc",
    ],
)
def test_roundtrip_codepoint21(base: int, text: str) -> None:
    code = encode(text, base=base)
    assert decode(code, base=base) == text


def test_hash_roundtrip() -> None:
    code = encode("test", base=2, has_hash=True)
    assert decode(code, base=2) == "test"


def test_hash_roundtrip_base36() -> None:
    code = encode("test", base=36, has_hash=True)
    assert decode(code, base=36) == "test"


def test_wrong_base_fails() -> None:
    code = encode("test", base=5)
    with pytest.raises(ValueError):
        decode(code, base=7)


def test_corruption_detected() -> None:
    code = encode("integrity check", base=2)
    idx = 100
    flipped = "1" if code[idx] == "0" else "0"
    mutated = code[:idx] + flipped + code[idx + 1:]
    with pytest.raises(ValueError, match="CRC mismatch"):
        decode(mutated, base=2)


def test_trailing_data_rejected() -> None:
    code = encode("abc", base=2)
    extra = "0" * 32
    with pytest.raises(ValueError, match="trailing data"):
        decode(code + extra, base=2)


def test_surrogate_rejected_on_encode() -> None:
    with pytest.raises(ValueError, match="surrogate"):
        encode(chr(0xD800), base=2)


def test_surrogate_rejected_on_decode() -> None:
    from voxpolymachina.basecodec import bits_to_base
    from voxpolymachina.header import build_header
    from voxpolymachina.unicode_bits import TERMINATOR

    bad_payload = format(0xD800, "021b") + format(TERMINATOR, "021b")
    header = build_header(
        mode="codepoint21",
        block_size=1,
        payload_bits_str=bad_payload,
        has_hash=False,
    )
    code = bits_to_base(header.to_bits() + bad_payload, base=2)
    with pytest.raises(ValueError, match="surrogate"):
        decode(code, base=2)


def test_truncated_header_with_hash_rejected() -> None:
    """A stream cut between 96 and 160 bits must be rejected clearly."""
    code = encode("abc", base=2, has_hash=True)
    # 128 chars in base 2 = 128 bits = 4 full chunks, so base_to_bits
    # succeeds. The header with hash needs 160 bits, so parse_header
    # must reject this before reading past the end.
    truncated = code[:128]
    with pytest.raises(ValueError, match="too short"):
        decode(truncated, base=2)


def test_truncated_header_without_hash_rejected() -> None:
    """A stream cut below 96 bits must be rejected clearly."""
    code = encode("abc", base=2)
    # 64 chars = 64 bits = 2 chunks. Less than BASE_HEADER_BITS.
    truncated = code[:64]
    with pytest.raises(ValueError, match="too short"):
        decode(truncated, base=2)


# --- Configuration integration tests ---


def test_config_dict_overrides_defaults() -> None:
    cfg = {"base": {"default_base": 5}}
    code = encode("abc", config=cfg)
    assert decode(code, base=5) == "abc"


def test_config_dict_is_not_mutated() -> None:
    cfg = {"base": {"default_base": 5}, "text": {"mode": "codepoint21"}}
    snapshot = {"base": {"default_base": 5}, "text": {"mode": "codepoint21"}}
    encode("abc", config=cfg)
    assert cfg == snapshot


def test_config_default_base_used_in_decode() -> None:
    cfg = {"base": {"default_base": 16}}
    code = encode("abc", config=cfg)
    assert decode(code, config=cfg) == "abc"


def test_explicit_base_beats_config() -> None:
    cfg = {"base": {"default_base": 16}}
    code = encode("abc", base=5, config=cfg)
    assert decode(code, base=5, config=cfg) == "abc"
    with pytest.raises(ValueError):
        decode(code, config=cfg)


def test_config_none_does_no_file_io(tmp_path, monkeypatch) -> None:
    """config=None must neither write nor read config files."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.chdir(tmp_path)

    # Pre-create a global config that would force base 36 if read.
    cfg_dir = tmp_path / ".config" / "voxpolymachina"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(
        '{"base": {"default_base": 36}}', encoding="utf-8"
    )

    code = encode("abc")  # config=None
    # If the file had been read, the string would be base 36 and this
    # decode with base 2 would fail.
    assert decode(code, base=2) == "abc"


def test_config_auto_reads_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.chdir(tmp_path)

    encode("abc", config="auto")
    assert (tmp_path / ".config" / "voxpolymachina" / "config.json").exists()


def test_config_auto_respects_local_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.chdir(tmp_path)

    # Global says base 16, local overrides to base 5.
    cfg_dir = tmp_path / ".config" / "voxpolymachina"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(
        '{"base": {"default_base": 16}}', encoding="utf-8"
    )
    (tmp_path / "voxpolymachina.json").write_text(
        '{"base": {"default_base": 5}}', encoding="utf-8"
    )

    code = encode("abc", config="auto")
    # Both sides read the local override; no explicit base anywhere.
    assert decode(code, config="auto") == "abc"


def test_invalid_config_type_rejected() -> None:
    with pytest.raises(TypeError):
        encode("abc", config=42)


def test_unknown_config_string_rejected() -> None:
    with pytest.raises(TypeError, match="must be 'auto'"):
        encode("abc", config="sometimes")


def test_config_object_with_weird_eq_gets_type_error() -> None:
    """Objects whose __eq__ returns non-bool must not break the check."""

    class Weird:
        def __eq__(self, other):  # noqa: D105
            raise AssertionError("__eq__ should never be called")

    with pytest.raises(TypeError):
        encode("abc", config=Weird())

# --- Text mode tests: utf8 and ascii7 ---


@pytest.mark.parametrize("base", [2, 4, 16, 36])
@pytest.mark.parametrize(
    "text",
    ["", "A", "Hello, world", "Привет", "Привет 🌍", "a\tb\nc"],
)
def test_roundtrip_utf8(base: int, text: str) -> None:
    code = encode(text, base=base, mode="utf8", config=None)
    assert decode(code, base=base, config=None) == text


@pytest.mark.parametrize("base", [2, 4, 16, 36])
@pytest.mark.parametrize(
    "text",
    ["", "A", "Hello, world", "a\tb\nc", "12345"],
)
def test_roundtrip_ascii7(base: int, text: str) -> None:
    code = encode(text, base=base, mode="ascii7", config=None)
    assert decode(code, base=base, config=None) == text


def test_ascii7_rejects_non_ascii() -> None:
    with pytest.raises(ValueError, match="U\\+0000\\.\\.U\\+007F"):
        encode("Привет", base=16, mode="ascii7", config=None)


def test_utf8_rejects_surrogates() -> None:
    with pytest.raises(ValueError, match="UTF-8"):
        encode(chr(0xD800), base=16, mode="utf8", config=None)


def test_utf8_is_smaller_than_codepoint21_for_latin() -> None:
    text = "Hello, world"
    cp21 = encode(text, base=16, mode="codepoint21", config=None)
    u8 = encode(text, base=16, mode="utf8", config=None)
    assert len(u8) < len(cp21)


def test_ascii7_is_smallest_for_ascii() -> None:
    text = "Hello, world! This is a fairly long ASCII-only string."
    cp21 = encode(text, base=16, mode="codepoint21", config=None)
    u8 = encode(text, base=16, mode="utf8", config=None)
    a7 = encode(text, base=16, mode="ascii7", config=None)
    assert len(a7) < len(u8) < len(cp21)

def test_ascii7_is_smallest_for_ascii_long() -> None:
    text = "Hello, world! This is a fairly long ASCII-only string."
    cp21 = encode(text, base=16, mode="codepoint21", config=None)
    u8 = encode(text, base=16, mode="utf8", config=None)
    a7 = encode(text, base=16, mode="ascii7", config=None)
    assert len(a7) < len(u8) < len(cp21)