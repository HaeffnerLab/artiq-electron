#!/usr/bin/env python3
"""
pulse_designer.py
=================

Interactive designer for the Feedback-drive feedback-pulse *sequence*
(``pulse_sequence.PulseSpec``).  Drag the sliders, watch the expected drive
envelope update, then **Save** - it writes the ``pulse_*`` fields into a
``qick_standby`` config JSON that the RFSoC consumes verbatim.

Usage
-----
    python pulse_designer.py                     # start from defaults
    python pulse_designer.py my_config.json      # edit an existing standby config
    python pulse_designer.py -o out.json         # choose where Save writes

Works with a plain ``python`` (opens a matplotlib window) or inside Jupyter
(``%matplotlib widget`` then ``%run pulse_designer.py``).  Only needs
matplotlib + numpy.

The example from the brief - initial delay 1 ms, 3 x (1 ms on / 3 ms off) -
is ``initial_delay_us=1000, on_us=1000, off_us=3000, repeats=3``:
  * crossing -> last burst end : 10 ms   (tProc resumes monitoring here)
  * full grid incl. trailing off : 13 ms  (tick "count trailing off")
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import time

import matplotlib
# keep matplotlib off any STIX / Computer-Modern math fonts the user's matplotlibrc
# might point at but not have installed (avoids the findfont warning spam)
matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "mathtext.fontset": "dejavusans",
    "mathtext.default": "regular",
    "axes.unicode_minus": False,
})
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, RadioButtons, CheckButtons, Button, TextBox

from pulse_sequence import PulseSpec, SHAPES

# matplotlib backends that cannot show a window
_HEADLESS_BACKENDS = {"agg", "cairo", "pdf", "pgf", "ps", "svg", "template"}

# --------------------------------------------------------------------------- #
DEFAULT_CONFIG = {
    # a minimal standby config skeleton so a fresh Save is still usable
    "dac_pulse": 1, "adc_wait": 0, "adc_record": -1,
    "read_freq": 300.0, "pulse_freq": 300.0, "pulse_voltage": 0.8,
    "readout_length": 300, "metric": "absum", "v_thresh": "auto",
    "window_us": 2400.0, "pulse_when_disarmed": True, "mr_fallback": False,
}


def load_base(path: str | None) -> dict:
    if path and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return dict(DEFAULT_CONFIG)


def spec_from_base(base: dict) -> PulseSpec:
    try:
        return PulseSpec.from_config_fields(base)
    except Exception:
        return PulseSpec()


# --------------------------------------------------------------------------- #
#  exact-number API  --  type values in directly.  Nothing here is rounded or
#  step-quantised except ``repeats`` / ``ramp_steps`` (they index hardware
#  staircase counts and cannot be fractional).  The carrier frequency and every
#  ``*_us`` timing are kept as the exact Python float the caller gave.
# --------------------------------------------------------------------------- #
_INT_FIELDS = ("repeats", "ramp_steps")


def _coerce(attr: str, value):
    """Coerce a user-supplied value for PulseSpec field ``attr`` without
    rounding the precision-critical fields."""
    if attr in _INT_FIELDS:
        return int(round(float(value)))
    if attr == "count_trailing_off":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if attr == "shape":
        return str(value)
    if attr == "custom_points":
        return value
    return float(value)                       # exact -- no round(), no valstep


def _fmt_num(v) -> str:
    """Compact, precision-preserving string for a numeric field's text box."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f.is_integer() else f"{f:.10g}"


def make_spec(start=None, **fields) -> PulseSpec:
    """Build a :class:`PulseSpec` from explicit numbers, stored verbatim.

    ``start`` : a ``PulseSpec``, a standby-config ``dict``, a path to one, or
    ``None`` (defaults).  Every :class:`PulseSpec` field may be passed as a
    keyword; ``freq_mhz`` and the ``*_us`` timings keep full float precision
    (only ``repeats`` / ``ramp_steps`` are cast to ``int``).

        make_spec(freq_mhz=300.123456, initial_delay_us=1000.0,
                  on_us=1000.0, off_us=3000.0, repeats=3)
    """
    if isinstance(start, PulseSpec):
        base_spec = start
    elif isinstance(start, str):
        base_spec = spec_from_base(load_base(start))
    elif isinstance(start, dict):
        base_spec = spec_from_base(start)
    elif start is None:
        base_spec = PulseSpec()
    else:
        raise TypeError(f"start must be PulseSpec / dict / path / None, got {type(start)}")
    kw = dataclasses.asdict(base_spec)
    for k, v in fields.items():
        if k not in kw:
            raise KeyError(f"unknown PulseSpec field {k!r}; valid: {sorted(kw)}")
        kw[k] = _coerce(k, v)
    return PulseSpec(**kw)


def merge_config(base: dict, spec: PulseSpec) -> dict:
    """A standby-config dict: ``base`` updated with ``spec``'s ``pulse_*`` block
    (and the legacy ``pulse_length_us`` kept in sync)."""
    merged = dict(base)
    merged.update(spec.to_config_fields())
    merged["pulse_length_us"] = float(spec.on_us)
    return merged


def save_config(path: str, base: dict, spec: PulseSpec) -> str:
    """Write ``merge_config(base, spec)`` to ``path`` as JSON.  Returns ``path``."""
    with open(path, "w") as f:
        json.dump(merge_config(base, spec), f, indent=2)
    return path


def design(out_path: str, start=None, *, verbose: bool = True, **fields) -> str:
    """Headless pulse design: type the numbers, write the standby config, done.
    No GUI, no rounding of carrier frequency or timing.

        design("standby.json", "existing_cfg.json",
               freq_mhz=300.123456, initial_delay_us=1000.0, on_us=1000.0,
               off_us=3000.0, repeats=3, shape="trapezoid", ramp_us=50.0)
    """
    base = load_base(start) if (start is None or isinstance(start, str)) else dict(start)
    spec = make_spec(base, **fields)
    if verbose:
        print(spec.summary())
    save_config(out_path, base, spec)
    if verbose:
        print(f"[pulse_designer] wrote {out_path}")
    return out_path


# --------------------------------------------------------------------------- #
class Designer:
    SLIDERS = [
        # attr, label, min, max, step
        ("initial_delay_us", "initial delay [µs]", 0.0, 5000.0, 10.0),
        ("on_us",            "burst on [µs]",       1.0, 5000.0, 1.0),
        ("off_us",           "burst off [µs]",      0.0, 10000.0, 10.0),
        ("repeats",          "repeats",             1,   20,     1),
        ("ramp_us",          "ramp rise/fall [µs]", 0.0, 2000.0, 5.0),
        ("ramp_start_frac",  "ramp start [frac]",   0.0, 1.0,    0.01),
        ("ramp_steps",       "ramp steps",          4,   96,     1),
        ("gain_frac",        "peak amplitude [frac]", 0.0, 1.0,  0.01),
        ("freq_mhz",         "carrier [MHz]",       1.0, 1000.0, 1.0),
    ]

    def __init__(self, base: dict, out_path: str):
        self.base = base
        self.out_path = out_path
        self.spec = spec_from_base(base)
        self._last_draw = 0.0
        self._pending = False

        self.fig = plt.figure(figsize=(13.5, 8.4))
        try:
            self.fig.canvas.manager.set_window_title("feedback-pulse sequence designer")
        except Exception:
            pass
        self.ax = self.fig.add_axes([0.08, 0.46, 0.68, 0.47])

        # --- persistent artists (updated in place; NO ax.clear() on redraw) ---
        self.ax.set_xlabel("time after the threshold crossing  [µs]", fontsize=11)
        self.ax.set_ylabel("drive amplitude  (fraction of full scale)", fontsize=11)
        self.ax.set_ylim(-0.05, 1.30)
        self.ax.grid(alpha=0.3)
        self._delay_span = None
        self._bars = None
        (self._line,) = self.ax.plot([], [], color="tab:blue", lw=1.8)
        self.ax.axvline(0, color="0.3", ls="--", lw=1.2)
        self._resume_line = self.ax.axvline(0, color="tab:green", ls=":", lw=1.5)
        self._title = self.ax.set_title("", fontsize=11)
        self.ax.text(0.0, 1.0, "  crossing", transform=self.ax.get_xaxis_transform(),
                     ha="left", va="bottom", fontsize=8, color="0.3")

        # exact working values: the sliders AND the paired text boxes write here,
        # and the spec is always rebuilt from this dict -> a typed carrier
        # frequency or timing is used verbatim, never snapped to the slider step.
        self._exact = {a: _coerce(a, getattr(self.spec, a)) for a, *_ in self.SLIDERS}
        self._sync = False        # reentrancy guard while updating widgets in code

        # sliders (coarse drag) + a paired text box (exact entry), two columns
        self.sl, self.tx = {}, {}
        for i, (attr, label, lo, hi, step) in enumerate(self.SLIDERS):
            col, row = divmod(i, 5)
            x = 0.10 + col * 0.40
            y = 0.34 - row * 0.055
            axs = self.fig.add_axes([x, y, 0.185, 0.03])
            s = Slider(axs, label, lo, hi, valinit=float(self._exact[attr]),
                       valstep=step)
            s.valtext.set_visible(False)          # the text box shows the value
            s.on_changed(lambda v, a=attr: self._on_slider(a, v))
            self.sl[attr] = s
            axb = self.fig.add_axes([x + 0.205, y, 0.052, 0.03])
            b = TextBox(axb, "", initial=_fmt_num(self._exact[attr]))
            b.on_submit(lambda t, a=attr: self._on_text(a, t))
            self.tx[attr] = b
        self.fig.text(0.5, 0.378, "drag a slider for a coarse value  ·  type in its "
                      "box for an exact one  (carrier & timing are never rounded)",
                      ha="center", fontsize=8, color="0.4")

        # shape radio
        axr = self.fig.add_axes([0.83, 0.20, 0.15, 0.20]); axr.set_title("shape", fontsize=9)
        self.radio = RadioButtons(axr, SHAPES, active=SHAPES.index(self.spec.shape))
        self.radio.on_clicked(self._on_change)

        # trailing-off checkbox
        axc = self.fig.add_axes([0.83, 0.13, 0.15, 0.05])
        self.chk = CheckButtons(axc, ["count trailing off"], [self.spec.count_trailing_off])
        self.chk.on_clicked(self._on_change)

        # output path + save
        axt = self.fig.add_axes([0.13, 0.05, 0.50, 0.04])
        self.tb = TextBox(axt, "save to  ", initial=self.out_path)
        axb = self.fig.add_axes([0.66, 0.05, 0.12, 0.04])
        self.btn = Button(axb, "Save config")
        self.btn.on_clicked(self._save)
        self.ax_msg = self.fig.add_axes([0.79, 0.05, 0.19, 0.04]); self.ax_msg.axis("off")
        self._msg = self.ax_msg.text(0, 0.5, "", fontsize=9, va="center")

        self._redraw()

    # ------------------------------------------------------------------ #
    def _collect(self) -> PulseSpec:
        kw = dict(self._exact)      # exact values, not the quantised slider .val
        kw["shape"] = self.radio.value_selected
        kw["count_trailing_off"] = self.chk.get_status()[0]
        kw["custom_points"] = self.spec.custom_points
        return PulseSpec(**kw)

    # -- slider / text-box plumbing: both edit self._exact, then redraw -------- #
    def _on_slider(self, attr, v):
        if self._sync:
            return
        self._exact[attr] = _coerce(attr, v)
        self._set_text(attr)
        self._on_change()

    def _on_text(self, attr, text):
        if self._sync:
            return
        text = (text or "").strip()
        if not text:
            return
        try:
            val = _coerce(attr, text)
        except ValueError:
            self._msg.set_text(f"{attr}: not a number")
            self.fig.canvas.draw_idle()
            return
        self._exact[attr] = val
        self._set_slider(attr, val)
        self._on_change()

    def _set_text(self, attr):
        self._sync = True
        try:
            self.tx[attr].set_val(_fmt_num(self._exact[attr]))
        finally:
            self._sync = False

    def _set_slider(self, attr, val):
        s = self.sl[attr]
        self._sync = True
        try:
            s.set_val(min(max(float(val), s.valmin), s.valmax))   # visual only
        finally:
            self._sync = False

    def apply_exact(self, fields: dict):
        """Apply a dict of exact field -> value (e.g. from ``--set``) to the
        widgets and redraw, keeping full precision."""
        for k, v in fields.items():
            if k in self._exact:
                self._exact[k] = _coerce(k, v)
                self._set_slider(k, self._exact[k])
                self._set_text(k)
            elif k == "shape" and str(v) in SHAPES:
                self.radio.set_active(SHAPES.index(str(v)))
            elif k == "count_trailing_off":
                if _coerce(k, v) != self.chk.get_status()[0]:
                    self.chk.set_active(0)
            else:
                print(f"[pulse_designer] ignoring unknown field {k!r}")
        self.spec = self._collect()
        self._redraw()

    def _on_change(self, _evt=None):
        self.spec = self._collect()
        # throttle: at most ~20 redraws/s while a slider is dragged
        now = time.monotonic()
        if now - self._last_draw < 0.05:
            if not self._pending:
                self._pending = True
                t = self.fig.canvas.new_timer(interval=55)
                t.single_shot = True
                t.add_callback(self._deferred_draw)
                t.start()
                self._timer = t
            return
        self._redraw()

    def _deferred_draw(self):
        self._pending = False
        self.spec = self._collect()
        self._redraw()

    def _redraw(self):
        self._last_draw = time.monotonic()
        s = self.spec
        t, g = s.waveform(n=1200)
        self._line.set_data(t, g)

        # "on" windows as one collection (cheap: remove + re-add a single artist)
        if self._bars is not None:
            self._bars.remove()
        segs = [(a, max(b - a, 1e-6)) for a, b, _, _ in s.timeline()]
        self._bars = self.ax.broken_barh(segs, (0, 1.0), color="tab:blue", alpha=0.10,
                                         lw=0)

        # initial-delay grey span
        if self._delay_span is not None:
            self._delay_span.remove()
            self._delay_span = None
        if s.initial_delay_us > 0:
            self._delay_span = self.ax.axvspan(0, s.initial_delay_us, color="0.85",
                                               alpha=0.6, lw=0)

        self._resume_line.set_xdata([s.active_span_us(), s.active_span_us()])

        span = max(s.total_us(), s.active_span_us(), 1.0)
        self.ax.set_xlim(-0.03 * span, 1.05 * span)
        n_seg = len(s.timeline())
        self._title.set_text(
            f"span {s.active_span_us():.0f} µs   "
            f"(total {s.total_us():.0f} µs)   "
            f"{s.repeats} burst{'s' if s.repeats != 1 else ''}   "
            f"duty {100 * s.duty_cycle():.0f}%   first drive @ "
            f"{s.timeline()[0][0] if n_seg else 0:.0f} µs")
        self.fig.canvas.draw_idle()

    def _save(self, _evt=None):
        path = self.tb.text.strip() or self.out_path
        try:
            save_config(path, self.base, self.spec)
            png = os.path.splitext(path)[0] + ".pulse.png"
            self.fig.savefig(png, dpi=110)
            self._msg.set_text(f"saved -> {os.path.basename(path)}")
            print(f"[pulse_designer] wrote {path}\n[pulse_designer] preview  {png}")
        except OSError as e:
            self._msg.set_text(f"save failed: {e}")
        self.fig.canvas.draw_idle()


# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", nargs="?", help="existing standby config JSON to edit")
    ap.add_argument("-o", "--out", help="where Save writes (default: alongside input "
                    "or ./standby_pulse.json)")
    ap.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE",
                    dest="sets", help="set a PulseSpec field to an exact value "
                    "(repeatable), e.g. --set freq_mhz=300.123456 --set on_us=1000")
    ap.add_argument("--no-gui", action="store_true", help="apply --set, write the "
                    "config and exit -- fully scriptable, no window, no rounding")
    a = ap.parse_args(argv)

    base = load_base(a.config)
    out = a.out or a.config or "standby_pulse.json"

    overrides = {}
    for item in a.sets:
        if "=" not in item:
            ap.error(f"--set expects FIELD=VALUE, got {item!r}")
        k, v = item.split("=", 1)
        overrides[k.strip()] = v.strip()

    if a.no_gui:
        design(out, base, **overrides)
        return

    d = Designer(base, out)
    if overrides:
        d.apply_exact(overrides)
    backend = matplotlib.get_backend().lower()
    if backend in _HEADLESS_BACKENDS:
        # no GUI available - write the config, render a static preview, print spec
        save_config(out, d.base, d.spec)
        print(d.spec.summary())
        d.fig.savefig("pulse_preview.png", dpi=110)
        print(f"[pulse_designer] non-GUI backend ({backend}); wrote {out} + "
              "pulse_preview.png. For the interactive sliders, run with a GUI "
              "backend (e.g. `pip install PyQt5` or set MPLBACKEND=TkAgg).")
        return
    print(f"[pulse_designer] backend {backend} - drag the sliders, then 'Save config'.")
    plt.show()


if __name__ == "__main__":
    main()
