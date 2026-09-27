"""Command-line interface for voxpolymachina."""
from __future__ import annotations

import json

import typer

from . import __version__
from . import decode as _decode
from . import encode as _encode
from .config import ensure_global_config, load_config

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