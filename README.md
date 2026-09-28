# voxpolymachina

Bidirectional codec: text to bits to base-N string to audio (MFSK over WAV),
and back. Written in pure Python with a small `typer` CLI on top. Audio
output is standard 16-bit PCM WAV; no external audio libraries required.

## Status

v0.5.3 — text layer and audio layer work end to end for synthetic WAVs.
Real acoustic transmission (speaker to microphone) is possible but not
robust; see "Known limitations" below.

## Install

    pip install voxpolymachina

For development, clone the repository and install in editable mode:

    git clone https://github.com/frozenwork-hash/VoxPolyMachina.git
    cd VoxPolyMachina
    pip install -e ".[dev]"

The codec itself uses only the Python standard library. There are no
required runtime dependencies beyond `typer` for the CLI.

The `audio` extra (`numpy`, `sounddevice`) is not required by v0.4.
Everything runs on the standard library.

## Command-line usage

    # Encode text as a base-N string and back
    vpm encode "Ave Drago Nihilus" --base 16
    vpm decode "<string>" --base 16

    # Encode text as audio and back
    vpm audio-encode "Ave Drago Nihilus" --out drago.wav --style adeptus
    vpm audio-decode drago.wav --style adeptus

    # Inspect a WAV
    vpm audio-info drago.wav

    # List all available styles
    vpm styles

    # Configuration
    vpm config --show
    vpm config --path

Text modes: `codepoint21` (default, universal), `utf8`, `ascii7`.
Bases: 2..36.

## Library usage

    from voxpolymachina import encode, decode

    code = encode("hello", base=16)
    text = decode(code, base=16)

    from voxpolymachina.audio import audio_encode, audio_decode

    audio_encode("hello", "out.wav", style="adeptus")
    text = audio_decode("out.wav", style="adeptus")

    # Get samples directly, for embedding in another program
    samples, sample_rate = audio_encode(
        "hello", inline=True, style="necron_scarab"
    )

`audio_encode(..., inline=True)` returns `(list[float], int)`.
`audio_encode(..., path=...)` writes a WAV and returns `None`.

## How it works

The codec is a stack of independent layers:

    text  <-> bits         unicode_bits.py + header.py
    bits  <-> base-N       basecodec.py
    base-N <-> tones       audio/fsk.py
    tones <-> WAV          audio/wav.py
    synchronisation        audio/preamble.py
    orchestration          audio/codec.py

Each layer is tested in isolation.

**Text layer.** `codepoint21` stores every Unicode code point as exactly
21 bits plus a terminator; `utf8` and `ascii7` store bytes. All modes end
with a header that carries magic, version, mode, block size, payload
length, CRC32, and an optional SHA-256 prefix. The header is part of the
same base-N string as the payload, so the output is homogeneous.

**Audio layer.** The base-N string is split into symbols. Each symbol
is one tone drawn from a linear frequency grid. The tone sequence is
prepended with a preamble: a fast two-tone trill followed by a short
silence. The silence is what disambiguates the trill's position (a
trill is periodic, so without a gap the detector has no unique answer).
Demodulation uses the Goertzel algorithm per symbol window — cheaper
than a full FFT when only a few frequencies matter.

**Text base and audio base are independent.** `base.default_base`
controls only the string form produced by `vpm encode`. `audio.base`
controls the number of tones. They do not have to match. The pipeline
is `text -> bits -> base-N string -> tones`; the text-layer base never
enters the audio stream.

## Styles

A style is a named bundle of audio-layer parameters: base, frequency
grid, symbol duration, waveform, preamble settings. Selecting a style
is equivalent to setting all of those by hand.

    vpm styles

Styles marked *decorative* encode to audio but cannot be decoded
reliably. Two reasons: the symbol rate is too fast for the chosen
frequency grid (e.g. `bell103`), or the waveform has harmonics that
overlap the grid (e.g. `sawtooth_rich`). Decorative styles exist for
their sound, not for round-trip.

Selected styles:

| Name          | Base | Description                                                 |
|---------------|------|-------------------------------------------------------------|
| `bell103`     | 2    | US Bell 103 modem, 300 baud *(decorative)*                  |
| `v21`         | 2    | ITU-T V.21 modem, 300 baud *(decorative)*                   |
| `fax`         | 2    | Fax handshake tones, 1100/2100 Hz                           |
| `morse`       | 2    | Morse-code beeps, 150/600 Hz slow pulses                    |
| `modem_v93`   | 4    | V.93-like 4-tone modem                                      |
| `r2d2`        | 2    | Fast high-pitched chirps                                    |
| `teletype`    | 2    | Teleprinter clatter, square 600/1200 Hz                     |
| `binary`      | 2    | Simple 0/1 beeps, square, 1000/2000 Hz                      |
| `electronic`  | 4    | Sci-fi 4-tone electronic chatter                            |
| `alien`       | 8    | Xenotech 8-tone triangle chatter                            |
| `sawtooth_rich` | 2  | Harsh sawtooth chatter *(decorative)*                       |
| `adeptus`     | 2    | Adeptus Mechanicus binary cant, terse square beeps *(WH40K)*|
| `servo_skull` | 2    | Servo-skull whine, fast high chirps *(WH40K)*               |
| `bolter`      | 2    | Bolter rounds, sharp aggressive bursts *(WH40K)*            |
| `chainsword`  | 2    | Chainsword grind, harsh sawtooth *(WH40K, decorative)*      |
| `lascannon`   | 2    | Lascannon discharge, sharp high-energy sine *(WH40K)*       |
| `vox_caster`  | 2    | Military vox chatter, two-tone radio *(WH40K)*              |
| `auspex`      | 2    | Auspex sonar pings, slow sweep *(WH40K)*                    |
| `servitor`    | 2    | Servitor drone, dull monotone *(WH40K)*                     |
| `titan`       | 2    | God-Machine rumble, deep sub-bass *(WH40K)*                 |
| `noosphere`   | 4    | Noosphere data stream, 4-tone fast *(WH40K)*                |
| `skitarii`    | 2    | Skitarii march, mechanical square pulses *(WH40K)*          |
| `dataspike`   | 2    | Dataspike injection, ultra-fast harsh *(WH40K, decorative)* |
| `omnissiah`   | 2    | Sacred binary cant, ritual tones *(WH40K)*                  |
| `necron_scarab` | 8  | Necron Scarab swarm, dissonant sub-bass drone *(WH40K, decorative)* |
| `necron`      | 12   | Awakening tomb world, slow inhuman drone *(WH40K, decorative)* |

Note on WH40K: Warhammer 40,000, Adeptus Mechanicus, Servo-skull,
Bolter, Chainsword, Lascannon, Vox-caster, Auspex, Servitor, Titan,
Noosphere, Skitarii, Dataspike, Omnissiah, Necron, Necron Scarab, and
related names are trademarks or registered trademarks of Games
Workshop Ltd. They are used here purely for descriptive,
non-commercial, referential purposes. This project is not affiliated
with, endorsed by, or sponsored by Games Workshop.

## Configuration

Configuration is JSON. Precedence, lowest to highest:

1. Built-in defaults (`config.py`)
2. Global config file, auto-created by the CLI on first use
3. Local config file `voxpolymachina.json` in the current directory
4. Explicit `config={...}` dict passed to library calls

From the library, `encode` and `decode` accept:

    config=None      built-in defaults only; no file I/O
    config="auto"    read global and local files (CLI uses this)
    config={...}     merge the given dict over built-in defaults

Global config path: `$XDG_CONFIG_HOME/voxpolymachina/config.json`, or
`~/.config/voxpolymachina/config.json` if `XDG_CONFIG_HOME` is unset.
On Windows, `~` resolves via `USERPROFILE`.

## Audio parameters

Passed as CLI options, config fields, or `audio_encode`/`audio_decode`
keyword arguments. When a style is selected, style fields override
config, and explicit keyword arguments override style.

    audio_base       2..36, number of tones
    frequencies      comma-separated list, one per symbol; overrides
                     f_min/f_max
    f_min, f_max     endpoints of the linear frequency grid
    symbol_ms        duration of one symbol in milliseconds
    waveform         sine | square | sawtooth | triangle
    sample_rate      Hz, default 44100
    amplitude        0..1
    fade_ms          per-symbol linear fade, avoids clicks
    preamble_mode    trill | none
    preamble_repeats number of a-b pairs in the trill

Command-line example with an explicit grid:

    vpm audio-encode "hello" -o out.wav --audio-base 2 --freqs "800,2500"
    vpm audio-decode out.wav --audio-base 2 --freqs "800,2500"

## Known limitations

- **No real-channel transmission robustness.** The codec works
  perfectly on synthetic WAVs. Through a speaker and microphone, the
  signal picks up noise, echo, and AGC effects; the decoder currently
  has no error correction. Short messages at base 2 with `--symbol-ms`
  of 50-200 ms and a narrow frequency range (e.g. 800..2500 Hz) may
  get through; longer or denser messages will not. FEC and channel
  equalisation are future work.
- **Decoder does not auto-detect base or frequencies.** Both must be
  supplied by the caller, either explicitly or via a style. This is by
  design: the base cannot be stored in the header, because the header
  itself has to be decoded first.
- **Surrogate code points (U+D800..U+DFFF) are rejected** on both
  encode and decode, in every text mode. They are not valid Unicode
  scalar values and cannot be round-tripped safely.
- **Two decorative-only modes exist in v0.4**: very fast symbol rates
  (bell103, v21, dataspike) and harmonic-rich waveforms
  (chainsword, sawtooth_rich). They sound right but do not decode.
- **Sub-bass styles** (`titan`, `necron`, `necron_scarab`) need
  headphones or full-range speakers. Laptop speakers will not
  reproduce frequencies below ~200 Hz.

## Development

Run the test suite:

    pytest -q

Generate one WAV per style for a phrase, for listening:

    python scripts/gen_styles.py
    python scripts/gen_styles.py --out-dir my_folder --text "Other phrase"

Output files are named `Ave_<style>.wav` in the target directory
(default `TestWav/`).

## License

MIT.

## Acknowledgements

Built in dialogue with an AI assistant (**DeepSeek**). The header layout, the split
between text base and audio base, the preamble silence gap, the style
preset system, and the WH40K-themed presets all came out of that
back-and-forth. Many of the trickier bugs were caught there too. The
bugs that remain are, of course, mine.