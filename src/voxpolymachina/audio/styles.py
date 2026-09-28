"""Predefined audio style presets.

Each style bundles the audio-layer parameters into a single name:
base, frequencies, symbol duration, waveform, and preamble settings.
Selecting a style is equivalent to setting all those parameters by
hand, but the code stays readable and reproducible.


Styles are free-form; the numbers are chosen for character, not for
protocol compatibility. Some styles are `decodable=False`: they encode
to audio but cannot be decoded reliably, either because their symbol
rate is too fast for the frequency grid (bell103, v21, dataspike) or
because their waveform has harmonics that overlap the symbol grid
(chainsword, sawtooth_rich). Some others are marked `decodable=False`
because they are meant to sound alien or wrong and are not intended
for round-trip (necron, necron_scarab).

--------------------------------------------------------------------------
Warhammer 40,000, Adeptus Mechanicus, Servo-skull, Bolter, Chainsword,
Lascannon, Vox-caster, Auspex, Servitor, Titan, Noosphere, Skitarii,
Dataspike, Omnissiah, Necron, Necron Scarab, and related names are
trademarks or registered trademarks of Games Workshop Ltd. 
They are used here purely for descriptive, non-commercial, 
referential purposes. This projectis not affiliated with, endorsed 
by, or sponsored by Games Workshop.
--------------------------------------------------------------------------

"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Style:
    name: str
    description: str
    audio_base: int
    frequencies: list[float]
    symbol_ms: float
    waveform: str = "sine"
    sample_rate: int = 44100
    amplitude: float = 0.6
    fade_ms: float = 5.0
    preamble_mode: str = "trill"
    preamble_repeats: int = 6
    decodable: bool = True

STYLES: dict[str, Style] = {
    "bell103": Style(
        name="bell103",
        description="US Bell 103 modem: 2-FSK, 300 baud, clean sine",
        audio_base=2,
        frequencies=[1070.0, 1270.0],
        symbol_ms=3.33,
        decodable = False
    ),
    "v21": Style(
        name="v21",
        description="ITU-T V.21 modem: 2-FSK, 300 baud, clean sine",
        audio_base=2,
        frequencies=[980.0, 1180.0],
        symbol_ms=3.33,
        decodable = False
    ),
    "fax": Style(
        name="fax",
        description="Fax handshake tones, 1100/2100 Hz",
        audio_base=2,
        frequencies=[1100.0, 2100.0],
        symbol_ms=5.0,
    ),
    "modem_v93": Style(
        name="modem_v93",
        description="V.93-like 4-tone modem",
        audio_base=4,
        frequencies=[500.0, 1500.0, 2500.0, 3500.0],
        symbol_ms=8.0,
    ),
    "r2d2": Style(
        name="r2d2",
        description="Fast high-pitched chirps",
        audio_base=2,
        frequencies=[800.0, 3200.0],
        symbol_ms=15.0,
        waveform="square",
    ),
    "teletype": Style(
        name="teletype",
        description="Teleprinter clatter, square 600/1200 Hz",
        audio_base=2,
        frequencies=[600.0, 1200.0],
        symbol_ms=20.0,
        waveform="square",
    ),
    "binary": Style(
        name="binary",
        description="Simple 0/1 beeps, square, 1000/2000 Hz",
        audio_base=2,
        frequencies=[1000.0, 2000.0],
        symbol_ms=50.0,
        waveform="square",
    ),
    "electronic": Style(
        name="electronic",
        description="Sci-fi 4-tone electronic chatter",
        audio_base=4,
        frequencies=[400.0, 1200.0, 2400.0, 4800.0],
        symbol_ms=25.0,
        waveform="square",
    ),
    "alien": Style(
        name="alien",
        description="Xenotech 8-tone triangle chatter",
        audio_base=8,
        frequencies=[
            300.0, 800.0, 1400.0, 2000.0,
            2600.0, 3200.0, 3800.0, 4000.0,
        ],
        symbol_ms=12.0,
        waveform="triangle",
    ),
    "adeptus": Style(
        name="adeptus",
        description=(
                "Adeptus Mechanicus binary cant, terse square beeps" 
                "(WH40K; TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[1800.0, 2400.0],
        symbol_ms=12.0,
        waveform="square",
    ),
    "sawtooth_rich": Style(
        name="sawtooth_rich",
        description="Harsh sawtooth chatter, base 2",
        audio_base=2,
        frequencies=[600.0, 2500.0],
        symbol_ms=18.0,
        waveform="sawtooth",
        decodable = False
    ),

        # --- Warhammer 40,000 themed styles (see copyright note above) ---

    "servo_skull": Style(
        name="servo_skull",
        description=(
            "Servo-skull whine, fast high chirps (WH40K; "
            "TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[3000.0, 5500.0],
        symbol_ms=8.0,
    ),
    "bolter": Style(
        name="bolter",
        description=(
            "Bolter rounds, sharp aggressive bursts (WH40K; "
            "TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[350.0, 850.0],
        symbol_ms=12.0,
        waveform="square",
    ),
    "chainsword": Style(
        name="chainsword",
        description=(
            "Chainsword grind, harsh sawtooth (WH40K; TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[200.0, 500.0],
        symbol_ms=20.0,
        waveform="sawtooth",
        decodable=False,
    ),
    "lascannon": Style(
        name="lascannon",
        description=(
            "Lascannon discharge, sharp high-energy sine (WH40K; "
            "TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[2200.0, 4400.0],
        symbol_ms=15.0,
    ),
    "vox_caster": Style(
        name="vox_caster",
        description=(
            "Military vox chatter, two-tone radio (WH40K; "
            "TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[800.0, 1800.0],
        symbol_ms=40.0,
    ),
    "auspex": Style(
        name="auspex",
        description=(
            "Auspex sonar pings, slow sweep (WH40K; TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[1200.0, 2400.0],
        symbol_ms=60.0,
    ),
    "servitor": Style(
        name="servitor",
        description=(
            "Servitor drone, dull monotone (WH40K; TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[200.0, 400.0],
        symbol_ms=100.0,
    ),
        "morse": Style(
        name="morse",
        description=(
            "Morse-code beeps, 150/600 Hz slow pulses"
        ),
        audio_base=2,
        frequencies=[150.0, 600.0],
        symbol_ms=60.0,
    ),
    "titan": Style(
        name="titan",
        description=(
            "God-Machine rumble, deep sub-bass (WH40K; "
            "TM Games Workshop). Needs headphones or full-range "
            "speakers; laptop speakers will not reproduce 60 Hz."
        ),
        audio_base=2,
        frequencies=[60.0, 180.0],
        symbol_ms=120.0,
    ),
        "necron_scarab": Style(
        name="necron_scarab",
        description=(
            "Necron Scarab swarm, dissonant 8-tone sub-bass drone "
            "(WH40K; TM Games Workshop). Decorative only."
        ),
        audio_base=8,
        frequencies=[
            50.0, 90.0, 140.0, 210.0,
            320.0, 480.0, 700.0, 1000.0,
        ],
        symbol_ms=180.0,
        waveform="triangle",
        decodable=False,
    ),
    "necron": Style(
        name="necron",
        description=(
            "Awakening tomb world, 12-tone deep drone, slow and "
            "inhuman (WH40K; TM Games Workshop). Decorative only. "
            "Needs sub-bass-capable output."
        ),
        audio_base=12,
        frequencies=[
            50.0, 73.0, 101.0, 144.0, 199.0, 283.0,
            401.0, 552.0, 749.0, 1003.0, 1338.0, 1759.0,
        ],
        symbol_ms=250.0,
        waveform="triangle",
        decodable=False,
    ),
    "noosphere": Style(
        name="noosphere",
        description=(
            "Noosphere data stream, 4-tone fast (WH40K; "
            "TM Games Workshop)"
        ),
        audio_base=4,
        frequencies=[500.0, 1500.0, 2500.0, 3500.0],
        symbol_ms=12.0,
    ),
    "skitarii": Style(
        name="skitarii",
        description=(
            "Skitarii march, mechanical square pulses (WH40K; "
            "TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[800.0, 2000.0],
        symbol_ms=15.0,
        waveform="square",
    ),
    "dataspike": Style(
        name="dataspike",
        description=(
            "Dataspike injection, ultra-fast harsh (WH40K; "
            "TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[300.0, 900.0],
        symbol_ms=5.0,
        waveform="square",
        decodable=False,
    ),
    "omnissiah": Style(
        name="omnissiah",
        description=(
            "Sacred binary cant, ritual tones (WH40K; TM Games Workshop)"
        ),
        audio_base=2,
        frequencies=[1200.0, 2400.0],
        symbol_ms=30.0,
        preamble_repeats=8,
    ),
}


def get_style(name: str) -> Style:
    if name not in STYLES:
        available = ", ".join(sorted(STYLES))
        raise ValueError(
            f"unknown style {name!r}; available: {available}"
        )
    return STYLES[name]


def list_styles() -> list[Style]:
    return [STYLES[k] for k in sorted(STYLES)]