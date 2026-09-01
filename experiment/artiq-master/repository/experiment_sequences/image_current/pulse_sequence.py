"""
pulse_sequence.py
=================

The feedback-pulse *sequence* description, shared by

  * ``qick_standby.py``  - emits it on the tProc after a threshold crossing
  * ``pulse_designer.py`` - interactive preview + writes it into a standby config

Pure stdlib + numpy (no ``qick`` import) so it loads anywhere.

A sequence = ``initial_delay`` then ``repeats`` bursts of ``on_us`` separated by
``off_us``.  Each burst has a shape (const / ramp-up / ramp-down / trapezoid /
custom) built from piecewise-linear gain segments.  Time ``t = 0`` is the moment
the threshold decision fires (the ~few-µs hardware latency is separate; for a
sequence with a ms-scale ``initial_delay`` it is negligible).

Example (the one in the brief)::

    PulseSpec(initial_delay_us=1000, on_us=1000, off_us=3000, repeats=3)
    .total_us()                    -> 13000.0   (1 + 3*1 + 3*3)
    .total_us(count_trailing_off=False stored) or .active_span_us() -> 10000.0
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from typing import List, Tuple

import numpy as np

SHAPES = ("const", "ramp_up", "ramp_down", "trapezoid", "custom")

# gain-register full scale for axis_signal_gen_v6 (matches qick 'maxv')
FULL_SCALE = 32766


@dataclass
class PulseSpec:
    # --- amplitude / carrier ---
    gain_frac: float = 1.0          # peak amplitude, 0..1 of full scale
    freq_mhz: float = 300.0         # carrier / DDS frequency

    # --- sequence timing (microseconds) ---
    initial_delay_us: float = 0.0   # wait between the crossing and burst 1
    on_us: float = 2000.0           # on-time of each burst
    off_us: float = 0.0             # off-time between bursts
    repeats: int = 1                # number of bursts
    count_trailing_off: bool = False  # include the last off gap in total_us()

    # --- shape within a burst ---
    shape: str = "const"            # see SHAPES
    ramp_us: float = 0.0            # rise (and fall, for trapezoid) duration
    ramp_start_frac: float = 0.0    # ramp begins at this fraction of the peak
    ramp_steps: int = 48            # tProc staircase resolution for a ramp
    # for shape == "custom": breakpoints [(t_us_from_burst_start, gain_frac), ...]
    custom_points: List[Tuple[float, float]] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    def __post_init__(self):
        if self.shape not in SHAPES:
            raise ValueError(f"shape must be one of {SHAPES}, got {self.shape!r}")
        self.repeats = max(1, int(self.repeats))
        self.ramp_steps = int(np.clip(self.ramp_steps, 1, 256))

    # ------------------------------------------------------------------ #
    def _eff_ramp_us(self) -> float:
        """ramp time clamped so a burst stays self-consistent."""
        if self.shape in ("ramp_up", "ramp_down"):
            return float(min(self.ramp_us, self.on_us))
        if self.shape == "trapezoid":
            return float(min(self.ramp_us, self.on_us / 2.0))
        return 0.0

    def burst_segments(self) -> List[Tuple[float, float, float, float]]:
        """One burst starting at t=0: list of (t0, t1, g0, g1) linear gain ramps,
        gain as a fraction of full scale (peak == ``gain_frac``)."""
        g = float(self.gain_frac)
        s = float(self.ramp_start_frac) * g
        on = float(self.on_us)
        r = self._eff_ramp_us()

        if self.shape == "custom" and self.custom_points:
            pts = sorted((max(0.0, min(on, float(t))), float(gf) * g)
                         for t, gf in self.custom_points)
            if pts[0][0] > 0:
                pts.insert(0, (0.0, pts[0][1]))
            if pts[-1][0] < on:
                pts.append((on, pts[-1][1]))
            return [(pts[i][0], pts[i + 1][0], pts[i][1], pts[i + 1][1])
                    for i in range(len(pts) - 1) if pts[i + 1][0] > pts[i][0]]

        if self.shape == "const" or r <= 0:
            return [(0.0, on, g, g)]
        if self.shape == "ramp_up":
            return [(0.0, r, s, g)] + ([(r, on, g, g)] if on > r else [])
        if self.shape == "ramp_down":
            return ([(0.0, on - r, g, g)] if on > r else []) + [(on - r, on, g, s)]
        if self.shape == "trapezoid":
            mid = [(r, on - r, g, g)] if on > 2 * r else []
            return [(0.0, r, s, g)] + mid + [(on - r, on, g, s)]
        return [(0.0, on, g, g)]

    def timeline(self) -> List[Tuple[float, float, float, float]]:
        """Whole sequence: (t0, t1, g0, g1) segments, t=0 at the crossing. The
        off gaps are simply absent (gain 0)."""
        out: List[Tuple[float, float, float, float]] = []
        t = float(self.initial_delay_us)
        for i in range(self.repeats):
            for (a, b, g0, g1) in self.burst_segments():
                out.append((t + a, t + b, g0, g1))
            t += float(self.on_us)
            if i < self.repeats - 1 or self.count_trailing_off:
                t += float(self.off_us)
        return out

    def total_us(self) -> float:
        """Full sequence duration from the crossing (incl. initial delay; incl.
        the trailing off gap only if ``count_trailing_off``)."""
        t = float(self.initial_delay_us) + self.repeats * float(self.on_us)
        t += max(0, self.repeats - 1) * float(self.off_us)
        if self.count_trailing_off:
            t += float(self.off_us)
        return t

    def active_span_us(self) -> float:
        """crossing -> end of the last burst (never counts a trailing off)."""
        return (float(self.initial_delay_us) + self.repeats * float(self.on_us)
                + max(0, self.repeats - 1) * float(self.off_us))

    def duty_cycle(self) -> float:
        span = self.active_span_us() - float(self.initial_delay_us)
        return (self.repeats * float(self.on_us) / span) if span > 0 else 0.0

    def waveform(self, n: int = 4000, pad_frac: float = 0.03):
        """Dense (t_us, gain_frac) for plotting; off gaps are 0."""
        T = max(self.total_us(), self.active_span_us(), 1.0)
        t = np.linspace(-pad_frac * T, T * (1 + pad_frac), int(n))
        g = np.zeros_like(t)
        for (a, b, g0, g1) in self.timeline():
            m = (t >= a) & (t <= b)
            g[m] = g0 + (g1 - g0) * (t[m] - a) / max(b - a, 1e-9)
        return t, g

    def summary(self) -> str:
        segs = self.timeline()
        lines = [
            f"shape={self.shape}  repeats={self.repeats}  gain={self.gain_frac:.3f}"
            f"  f={self.freq_mhz} MHz",
            f"initial_delay = {self.initial_delay_us:g} us",
            f"per burst: on = {self.on_us:g} us   off = {self.off_us:g} us"
            + (f"   ramp = {self.ramp_us:g} us ({self.ramp_steps} steps)"
               if self.shape != "const" else ""),
            f"crossing -> last burst end : {self.active_span_us():g} us",
            f"total (as stored)          : {self.total_us():g} us",
            f"duty cycle                 : {100 * self.duty_cycle():.1f} %",
            f"first drive at t = {segs[0][0]:g} us" if segs else "no bursts",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  (de)serialisation - as a flat ``pulse_*`` block for StandbyConfig
    # ------------------------------------------------------------------ #
    _FIELD_MAP = {
        "gain_frac": "pulse_voltage",
        "freq_mhz": "pulse_freq",
        "initial_delay_us": "pulse_initial_delay_us",
        "on_us": "pulse_on_us",
        "off_us": "pulse_off_us",
        "repeats": "pulse_repeats",
        "count_trailing_off": "pulse_count_trailing_off",
        "shape": "pulse_shape",
        "ramp_us": "pulse_ramp_us",
        "ramp_start_frac": "pulse_ramp_start_frac",
        "ramp_steps": "pulse_ramp_steps",
        "custom_points": "pulse_custom_points",
    }

    def to_config_fields(self) -> dict:
        d = asdict(self)
        return {self._FIELD_MAP[k]: v for k, v in d.items()}

    @classmethod
    def from_config_fields(cls, cfg: dict) -> "PulseSpec":
        inv = {v: k for k, v in cls._FIELD_MAP.items()}
        kw = {}
        for cfg_key, spec_key in inv.items():
            if cfg_key in cfg and cfg[cfg_key] is not None:
                kw[spec_key] = cfg[cfg_key]
        # back-compat: no pulse_on_us -> fall back to pulse_length_us
        if "on_us" not in kw and cfg.get("pulse_length_us") is not None:
            kw["on_us"] = cfg["pulse_length_us"]
        if kw.get("on_us", 0) is not None and float(kw.get("on_us", -1)) < 0:
            kw["on_us"] = cfg.get("pulse_length_us", 2000.0)
        return cls(**kw)

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def from_json(cls, path: str) -> "PulseSpec":
        with open(path) as f:
            return cls(**json.load(f))


def is_simple(spec: PulseSpec) -> bool:
    """True when the sequence is exactly the legacy 'one flat burst' - lets
    qick_standby keep its minimal-latency single-pulse fast path unchanged."""
    return (spec.repeats == 1 and spec.initial_delay_us == 0.0
            and spec.off_us == 0.0 and spec.shape == "const")
