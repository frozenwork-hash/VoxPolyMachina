"""Command-line interface for voxpolymachina."""
from __future__ import annotations

import json

import typer

from . import __version__
from . import decode as _decode
from . import encode as _encode
from .config import ensure_global_config, load_config
from .audio import audio_decode, audio_encode, audio_info
from .audio.styles import STYLES

app = typer.Typer(
    add_completion=False,
    help="voxpolymachina: text <-> base N codec (audio in later versions)",
)


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command("encode")
def encode_command(
    text: str = typer.Argument(..., help="Text to encode"),
    base: int | None = typer.Option(None, "--base", "-b", help="Base (2..36)"),
    mode: str | None = typer.Option(None, "--mode", "-m", help="Text mode"),
    block_size: int | None = typer.Option(
        None, "--block", help="Block size: 1, 2, or 4"
    ),
    use_hash: bool = typer.Option(False, "--hash", help="Include SHA-256 prefix"),
) -> None:
    """Encode text into a base-N string."""
    kwargs: dict = {"has_hash": use_hash, "config": "auto"}
    if base is not None:
        kwargs["base"] = base
    if mode is not None:
        kwargs["mode"] = mode
    if block_size is not None:
        kwargs["block_size"] = block_size
    try:
        typer.echo(_encode(text, **kwargs))
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1)


@app.command("decode")
def decode_command(
    code: str = typer.Argument(..., help="Base-N string to decode"),
    base: int | None = typer.Option(
        None,
        "--base",
        "-b",
        help="Base (2..36). If omitted, uses base.default_base from config.",
    ),
) -> None:
    """Decode a base-N string back into text."""
    kwargs: dict = {"config": "auto"}
    if base is not None:
        kwargs["base"] = base
    try:
        typer.echo(_decode(code, **kwargs))
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1)

@app.command("audio-encode")
def audio_encode_command(
    text: str = typer.Argument(..., help="Text to encode"),
    out: str = typer.Option(..., "--out", "-o", help="Output WAV path"),
    audio_base: int | None = typer.Option(
        None, "--audio-base", help="Number of tones, 2..36 (default from config)"
    ),
    sample_rate: int | None = typer.Option(
        None, "--sample-rate", help="Sample rate in Hz"
    ),
    symbol_ms: float | None = typer.Option(
        None, "--symbol-ms", help="Symbol duration in milliseconds"
    ),
    preamble_mode: str | None = typer.Option(
        None, "--preamble", help="Preamble mode: trill | none"
    ),
        style: str | None = typer.Option(
        None,
        "--style",
        help=f"Style preset: {', '.join(sorted(STYLES))}",
    ),
    waveform: str | None = typer.Option(
        None,
        "--waveform",
        help="Waveform: sine | square | sawtooth | triangle",
    ),
    freqs: str | None = typer.Option(
        None,
        "--freqs",
        help=(
            "Comma-separated frequencies in Hz, one per symbol, "
            "e.g. '1000,2000'. Length must equal --audio-base. "
            "Overrides config audio.f_min/f_max."
        ),
    ),
) -> None:
    """Encode text into a WAV file."""
    kwargs: dict = {"config": "auto"}
    if audio_base is not None:
        kwargs["audio_base"] = audio_base
    if sample_rate is not None:
        kwargs["sample_rate"] = sample_rate
    if symbol_ms is not None:
        kwargs["symbol_ms"] = symbol_ms
    if preamble_mode is not None:
        kwargs["preamble_mode"] = preamble_mode
    if style is not None:
        kwargs["style"] = style
    if waveform is not None:
        kwargs["waveform"] = waveform
    if freqs is not None:
        try:
            kwargs["frequencies"] = _parse_freqs(freqs)
        except ValueError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1)
    try:
        audio_encode(text, out, **kwargs)
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"wrote {out}")


@app.command("audio-decode")
def audio_decode_command(
    path: str = typer.Argument(..., help="Input WAV path"),
    audio_base: int | None = typer.Option(
        None, "--audio-base", help="Number of tones, 2..36 (default from config)"
    ),
    style: str | None = typer.Option(
        None, "--style", help=f"Style preset: {', '.join(sorted(STYLES))}"
    ),
    freqs: str | None = typer.Option(
        None,
        "--freqs",
        help=(
            "Comma-separated frequencies in Hz, one per symbol, "
            "e.g. '1000,2000'. Length must equal --audio-base. "
            "Overrides config audio.f_min/f_max."
        ),
    ),
        debug: bool = typer.Option(
        False, "--debug", help="Print preamble detection diagnostics"
    ),
) -> None:
    """Decode a WAV file produced by audio-encode."""
    kwargs: dict = {"config": "auto"}
    if debug:
        kwargs["debug"] = True
    if audio_base is not None:
        kwargs["audio_base"] = audio_base
    if style is not None:
        from .audio.styles import STYLES
        s = STYLES.get(style)
        if s is not None and not s.decodable:
            typer.echo(
                f"warning: style {style!r} is decorative only and "
                "cannot be decoded reliably",
                err=True,
            )
        kwargs["style"] = style
    if freqs is not None:
        try:
            kwargs["frequencies"] = _parse_freqs(freqs)
        except ValueError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1)
    try:
        typer.echo(audio_decode(path, **kwargs))
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1)


@app.command("audio-info")
def audio_info_command(
    path: str = typer.Argument(..., help="Input WAV path"),
) -> None:
    """Show WAV metadata and preamble offset estimate."""
    try:
        info = audio_info(path, config="auto")
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(json.dumps(info, indent=2))

@app.command("parse-freqs")
def _parse_freqs(s: str) -> list[float]:
    """Parse '1000,2000' or '500, 700, 1900' into a list of floats."""
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        raise ValueError("empty --freqs value")
    try:
        return [float(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"invalid --freqs value {s!r}: {exc}") from exc

@app.command("styles")
def styles_command() -> None:
    """List available audio style presets."""
    for name in sorted(STYLES):
        s = STYLES[name]
        typer.echo(f"{name:14s} base={s.audio_base}  {s.description}")
    
@app.command("config")
def config_command(
    show: bool = typer.Option(False, "--show", help="Print the merged config"),
    path: bool = typer.Option(False, "--path", help="Print the global config path"),
) -> None:
    """Show or locate the configuration file."""
    global_path = ensure_global_config()
    if path:
        typer.echo(str(global_path))
        return
    if show:
        typer.echo(json.dumps(load_config(), indent=2))
        return
    typer.echo(f"global config: {global_path}")
    typer.echo("use --show to print the merged configuration")
