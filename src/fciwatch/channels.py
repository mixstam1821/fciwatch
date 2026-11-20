"""Which FCI channel is compared with which SEVIRI channel.

FCI and SEVIRI do not have exactly the same spectral bands. For example FCI has a
band centred near 10.5 um, while SEVIRI has one near 10.8 um. Because of this, the
brightness temperatures (BT) of the two instruments are NOT expected to be equal,
even if both are perfectly calibrated.

This is why fciwatch looks at how the difference CHANGES over time (drift), and not
at the absolute size of the difference. See docs/METHOD.md.

The centre wavelengths below are rounded, nominal values. They are only used to
show the size of the spectral shift in the report. They are not used in any
calculation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelPair:
    name: str  # short id used in CSV files and on the command line
    fci: str  # channel name in Satpy's 'fci_l1c_nc' reader
    seviri: str  # channel name in Satpy's 'seviri_l1b_native' reader
    fci_um: float  # nominal FCI centre wavelength, micrometres
    seviri_um: float  # nominal SEVIRI centre wavelength, micrometres
    # A fixed "reference scene temperature" in kelvin. The bias of a scene is
    # reported at this temperature (see stats.py). Any value inside the normal
    # range of the channel works; it only has to stay the same over time.
    ref_bt: float

    @property
    def centre_shift_um(self) -> float:
        return round(self.fci_um - self.seviri_um, 2)


# The 3.8 um channel is left out on purpose: in daytime it contains reflected
# sunlight, which would mix a solar signal into a thermal comparison.
_PAIRS = (
    ChannelPair("ir105_ir108", "ir_105", "IR_108", 10.5, 10.8, 280.0),
    ChannelPair("ir123_ir120", "ir_123", "IR_120", 12.3, 12.0, 280.0),
    ChannelPair("ir133_ir134", "ir_133", "IR_134", 13.3, 13.4, 255.0),
    ChannelPair("ir87_ir87", "ir_87", "IR_087", 8.7, 8.7, 280.0),
    ChannelPair("ir97_ir97", "ir_97", "IR_097", 9.7, 9.7, 255.0),
    ChannelPair("wv63_wv62", "wv_63", "WV_062", 6.3, 6.2, 240.0),
    ChannelPair("wv73_wv73", "wv_73", "WV_073", 7.35, 7.3, 255.0),
)

PAIRS: dict[str, ChannelPair] = {p.name: p for p in _PAIRS}

# The three channels used by default: the two split-window channels and the
# CO2 channel. These are the ones where drift matters most for users.
DEFAULT_PAIRS: tuple[str, ...] = ("ir105_ir108", "ir123_ir120", "ir133_ir134")


def get_pairs(names) -> list[ChannelPair]:
    """Turn a list of pair names into ChannelPair objects, with a clear error."""
    out = []
    for n in names:
        if n not in PAIRS:
            raise KeyError(f"Unknown channel pair '{n}'. Known pairs: {', '.join(PAIRS)}")
        out.append(PAIRS[n])
    return out
