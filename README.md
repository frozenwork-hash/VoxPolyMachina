# voxpolymachina

Bidirectional codec for text, digits, and (planned) audio.

## Status

v0.1.0 — text <-> bits <-> base N. Audio is not implemented yet.

## Install

    pip install -e ".[dev]"

## Use

    vpm encode "Привет 🌍" --base 5
    vpm decode "<base-5 string>" --base 5
    vpm config --show
    vpm config --path

As a library:

    from voxpolymachina import encode, decode
    code = encode("hello", base=16)
    text = decode(code, base=16)

## What works in v1

- `codepoint21` mode: every Unicode code point is 21 bits, universal,
  fixed-size, supports all languages and emoji.
- Bases 2..36, homogeneous stream (header and payload in the same base).
- Header with magic, version, mode, block size, payload length, CRC32,
  and optional SHA-256 prefix.
- Config in `~/.config/voxpolymachina/config.json`, auto-created by CLI.
- Local `voxpolymachina.json` overrides global.

## Configuration semantics

    config=None    built-in defaults only; no file I/O
    config="auto"  read global and local config files
    config={...}   merge the given dict over built-in defaults

## What is planned

- `utf8` and `ascii7` text modes.
- Adaptive FSK/MFSK audio encoding.
- Audio decoding (WAV/FLAC).
- "Binary trill" fast mode for base 2.

## Known limitations

- Decoder does not auto-detect base; it must be supplied.
- Surrogate code points (U+D800..U+DFFF) are rejected on both encode and
  decode. They are not valid Unicode scalar values and cannot be safely
  round-tripped. Support may return in a later format version.
- `config=None` uses built-in defaults only and performs no file I/O.
  Pass `config="auto"` to read or create files under
  `~/.config/voxpolymachina/`.
- No audio yet.

## Audio

MFSK over WAV, mono 16-bit PCM, stdlib only.

- Preamble: alternating two-tone trill for synchronisation, or none.
- Symbol timing recovered to within ~`symbol_samples / 8` samples. The
  decoder biases the payload start left by this margin, so sub-symbol
  jitter cannot break alignment. Sub-sample precision is not attempted.
- Two independent bases: `base.default_base` for the text layer (only
  affects the string form produced by `vpm encode`) and `audio.base` for
  the number of tones in the audio stream. They do not have to match.