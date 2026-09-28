"""Orchestration: text <-> WAV.

The only module in `audio/` that knows about all layers. It composes:

    text  <-> bits       (unicode_bits + header)
    bits  <-> base-N     (basecodec)
    base-N <-> tones     (fsk)
    tones <-> WAV        (wav)
    preamble             (preamble)
    style presets        (styles)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .._sentinel import _UNSET, _UnsetType, _resolve_config
from ..basecodec import base_to_bits, bits_to_base
from ..header import build_header, parse_header, verify_header
from ..unicode_bits import bits_to_text, text_to_bits
from .fsk import FSKParams, samples_to_symbols, symbols_to_samples
from .preamble import build_trill, find_preamble, preamble_params_from_fsk
from .styles import get_style
from .tones import concat
from .wav import info_wav, read_wav, write_wav


def _apply_style(cfg: dict, style_name: str) -> None:
    """Overwrite audio config fields with values from a style preset."""
    style = get_style(style_name)
    cfg["audio"]["base"] = style.audio_base
    cfg["audio"]["frequencies"] = list(style.frequencies)
    cfg["audio"]["symbol_ms"] = style.symbol_ms
    cfg["audio"]["waveform"] = style.waveform
    cfg["audio"]["sample_rate"] = style.sample_rate
    cfg["audio"]["amplitude"] = style.amplitude
    cfg["audio"]["fade_ms"] = style.fade_ms
    cfg["audio"]["preamble_mode"] = style.preamble_mode
    cfg["audio"]["preamble_repeats"] = style.preamble_repeats


def _resolve_freq_range(
    cfg_audio: dict, sample_rate: int
) -> tuple[float, float]:
    f_min = float(cfg_audio["f_min"])
    f_max = float(cfg_audio["f_max"])
    if cfg_audio.get("auto_range", False):
        limit = (sample_rate / 2.0) * 0.9
        if f_max > limit:
            f_max = limit
    return f_min, f_max


def _build_fsk(
    cfg: dict, audio_base: int, sample_rate: int, symbol_ms: float
) -> FSKParams:
    cfg_audio = cfg["audio"]
    common = dict(
        base=audio_base,
        symbol_ms=symbol_ms,
        sample_rate=sample_rate,
        amplitude=float(cfg_audio["amplitude"]),
        fade_ms=float(cfg_audio["fade_ms"]),
        waveform=cfg_audio.get("waveform", "sine"),
    )
    freqs = cfg_audio.get("frequencies")
    if freqs is not None:
        return FSKParams(frequencies_hz=list(freqs), **common)
    f_min, f_max = _resolve_freq_range(cfg_audio, sample_rate)
    return FSKParams(f_min=f_min, f_max=f_max, **common)


def _normalize_peak(samples: list[float], target: float = 0.9) -> list[float]:
    """Scale samples so the peak absolute value is `target`."""
    if not samples:
        return samples
    peak = max(abs(s) for s in samples)
    if peak < 1e-6:
        return samples
    scale = target / peak
    return [s * scale for s in samples]


def _prepare_cfg(
    config: Any,
    style: str | None,
    frequencies: list[float] | None | _UnsetType,
    waveform: str | _UnsetType,
) -> dict:
    cfg = _resolve_config(config)
    if style is not None:
        _apply_style(cfg, style)
    if not isinstance(frequencies, _UnsetType):
        cfg["audio"]["frequencies"] = frequencies
    if not isinstance(waveform, _UnsetType):
        cfg["audio"]["waveform"] = waveform
    return cfg


def audio_encode(
    text: str,
    path: str | Path | None = None,
    audio_base: int | _UnsetType = _UNSET,
    sample_rate: int | _UnsetType = _UNSET,
    symbol_ms: float | _UnsetType = _UNSET,
    preamble_mode: str | _UnsetType = _UNSET,
    frequencies: list[float] | None | _UnsetType = _UNSET,
    waveform: str | _UnsetType = _UNSET,
    style: str | None = None,
    inline: bool = False,
    config: Any = None,
) -> tuple[list[float], int] | None:
    """Encode text into a WAV file, or (samples, sample_rate) when inline=True.

    Precedence (low to high): DEFAULTS, config files or dict, style,
    explicit keyword arguments. `style` sets audio-layer fields only;
    passing `frequencies` or `waveform` alongside a style overrides
    just those fields.
    """
    if inline:
        if path is not None:
            raise ValueError("pass either path or inline=True, not both")
    elif path is None:
        raise ValueError("path is required unless inline=True")

    cfg = _prepare_cfg(config, style, frequencies, waveform)

    if isinstance(audio_base, _UnsetType):
        audio_base = cfg["audio"]["base"]
    if isinstance(sample_rate, _UnsetType):
        sample_rate = cfg["audio"]["sample_rate"]
    if isinstance(symbol_ms, _UnsetType):
        symbol_ms = cfg["audio"]["symbol_ms"]
    if isinstance(preamble_mode, _UnsetType):
        preamble_mode = cfg["audio"]["preamble_mode"]

    text_cfg = cfg["text"]
    payload = text_to_bits(
        text,
        mode=text_cfg["mode"],
        block_size=text_cfg["block_size"],
        normalization=text_cfg["normalization"],
    )
    header = build_header(
        mode=text_cfg["mode"],
        block_size=text_cfg["block_size"],
        payload_bits_str=payload,
        has_hash=False,
    )
    combined = header.to_bits() + payload
    audio_symbols = bits_to_base(combined, audio_base)

    fsk = _build_fsk(cfg, audio_base, sample_rate, symbol_ms)

    blocks: list[list[float]] = []
    pre_params = preamble_params_from_fsk(
        fsk, cfg["audio"]["preamble_repeats"], preamble_mode
    )
    if pre_params is not None:
        blocks.append(build_trill(pre_params))
    blocks.append(symbols_to_samples(audio_symbols, fsk))

    samples = concat(blocks)

    if inline:
        return samples, sample_rate

    write_wav(
        path,
        samples,
        sample_rate,
        amplitude=cfg["audio"]["amplitude"],
    )
    return None


def audio_decode(
    path: str | Path,
    audio_base: int | _UnsetType = _UNSET,
    frequencies: list[float] | None | _UnsetType = _UNSET,
    waveform: str | _UnsetType = _UNSET,
    style: str | None = None,
    debug: bool = False,
    config: Any = None,
) -> str:
    """Decode a WAV file produced by audio_encode."""
    cfg = _prepare_cfg(config, style, frequencies, waveform)

    if isinstance(audio_base, _UnsetType):
        audio_base = cfg["audio"]["base"]

    samples, sample_rate = read_wav(path)
    samples = _normalize_peak(samples)
    fsk = _build_fsk(
        cfg, audio_base, sample_rate, float(cfg["audio"]["symbol_ms"])
    )

    pre_params = preamble_params_from_fsk(
        fsk,
        cfg["audio"]["preamble_repeats"],
        cfg["audio"]["preamble_mode"],
    )
    if pre_params is None:
        start = 0
    else:
        found = find_preamble(samples, pre_params)
        if found is None:
            if debug:
                import json as _json
                from .preamble import find_preamble_debug
                info = find_preamble_debug(samples, pre_params)
                print(_json.dumps(info, indent=2))
            raise ValueError(
                "preamble not found. Check that audio_base, symbol_ms, "
                "and preamble_mode match the encoder, or that the file "
                "was produced by this codec."
            )
        start = found

    from ..basecodec import CHUNK_BITS, _width_for
    from ..header import BASE_HEADER_BITS

    n_per = fsk.symbol_samples
    width = _width_for(audio_base)
    available = len(samples) - start
    max_symbols = available // n_per
    if max_symbols <= 0:
        raise ValueError("no audio data after preamble")

    all_symbols = samples_to_symbols(
        samples[start : start + max_symbols * n_per],
        max_symbols,
        fsk,
    )

    min_chunks = BASE_HEADER_BITS // CHUNK_BITS
    max_chunks = max_symbols // width
    last_error: Exception | None = None

    for n_chunks in range(min_chunks, max_chunks + 1):
        n_syms = n_chunks * width
        syms = all_symbols[:n_syms]
        try:
            combined = base_to_bits(syms, audio_base)
            header, consumed = parse_header(combined)
            if consumed + header.payload_bits > len(combined):
                continue
            payload = combined[consumed : consumed + header.payload_bits]
            verify_header(header, payload)
            return bits_to_text(payload, mode=header.mode)
        except ValueError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise ValueError(
            f"could not find a valid payload (last error: {last_error})"
        )
    raise ValueError("no valid payload found in decoded audio")


def audio_info(path: str | Path, config: Any = None) -> dict:
    """WAV metadata plus preamble-offset estimate, if findable."""
    cfg = _resolve_config(config)
    info = info_wav(path)
    sample_rate = info["sample_rate"]

    fsk = _build_fsk(
        cfg,
        int(cfg["audio"]["base"]),
        sample_rate,
        float(cfg["audio"]["symbol_ms"]),
    )
    pre_params = preamble_params_from_fsk(
        fsk,
        cfg["audio"]["preamble_repeats"],
        cfg["audio"]["preamble_mode"],
    )
    if pre_params is None:
        info["preamble_mode"] = "none"
        info["preamble_offset"] = None
    else:
        samples, _ = read_wav(path)
        info["preamble_mode"] = cfg["audio"]["preamble_mode"]
        info["preamble_offset"] = find_preamble(samples, pre_params)

    return info