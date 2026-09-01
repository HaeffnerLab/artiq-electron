"""
feedback_experiments_rfsoc_calib.py
===================================

Standalone ARTIQ experiment: **calibrate the RFSoC standby-detector threshold**
against the background, with the signal source OFF, and publish the result so a
later feedback run can pick it up.

Why separate (this was previously done inside ``FeedbackWithRFSoC.prepare()``):

  * the background measurement needs a clean "signal off" moment; making it its
    own experiment lets you arrange that once, look at the number, and reuse it
    across many feedback runs instead of re-measuring (and re-timing signal-off)
    at the top of every run;
  * the calibration apparatus state (Valon power, tip V, bias ring, ...) can be
    set up here in ``rfsoc_calib_setup`` without touching the feedback pipeline.

Workflow
--------
1. Signal OFF.  Run ``CalibrateRFSoCThreshold`` (pick an ``rfsoc_calib_tag``,
   e.g. "shared").  It measures the background and stores:

       dataset  rfsoc_calib_<tag>_v_thresh        (persistent, broadcast)
       dataset  rfsoc_calib_<tag>_read_freq / _readout_length / _metric
       dataset  rfsoc_calib_<tag>                 (full calibration dict, JSON)
       dataset  rfsoc_v_thresh / rfsoc_calibration  (the "latest" pointers)
       file     rfsoc_calib_<tag>.json            (next to the ARTIQ results)
       board    standby_out/rfsoc_calib_<tag>/calibration.json + config.json

2. Run ``FeedbackWithRFSoC`` with ``rfsoc_use_external_calib = True`` and the
   same ``rfsoc_calib_tag``.  It reads the stored v_thresh (dataset first, then
   the board's calibration.json) and skips its own background measurement.
   ``rfsoc_read_freq`` / ``rfsoc_readout_length`` / ``rfsoc_metric`` MUST match
   what was used here -- v_thresh is the metric sum over the readout window.

All host code -- nothing runs on an ARTIQ kernel.  Needs ``ssh`` + an ssh alias
for the RFSoC (default "rfsoc"); same requirements as ``feedback_experiments_rfsoc``.
"""

import json
import os
import sys
import time

from artiq.experiment import *
from feedback_experiments import FeedbackExperiments
import artiq_rfsoc_standby as R
def _load_rfsoc_client(host: str):
    print("start connecting to RFSoC standby client on host %r" % host)
    d = os.environ.get(
        "RFSOC_STANDBY_CLIENT_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "jupyter_notebooks", "Feedback-drive"),
    )
    if d not in sys.path:
        sys.path.insert(0, d)
    import artiq_rfsoc_standby as R
    R.RFSOC_HOST = host
    print("connected to RFSoC standby client on host %r" % host)
    return R


class CalibrateRFSoCThreshold(EnvExperiment, FeedbackExperiments):
    """Measure the RFSoC detection background (signal OFF) and set v_thresh."""

    def build(self):
        FeedbackExperiments.build(self) 
        G = "RFSoC threshold calibration"
        self.setattr_argument("rfsoc_host", StringValue("rfsoc"), group=G)
        self.setattr_argument(
            "rfsoc_calib_tag", StringValue("shared"), group=G,
            tooltip="label for this calibration; datasets/files/board dir are keyed "
                    "on it so you can keep several. FeedbackWithRFSoC selects one "
                    "with the same rfsoc_calib_tag.")

        # -- detection config: MUST match the feedback run that will use this --
        self.setattr_argument(
            "rfsoc_read_freq",
            NumberValue(default=25.0, unit="MHz", scale=1, ndecimals=3, step=0.1),
            group=G, tooltip="downconversion freq of the detection readout "
                             "(the signal frequency as it reaches the RFSoC ADC)")
        self.setattr_argument(
            "rfsoc_readout_length",
            NumberValue(default=300, scale=1, ndecimals=0, step=10),
            group=G, tooltip="detection integration window [decimated samples]; "
                             "v_thresh is the metric sum over this window")
        self.setattr_argument(
            "rfsoc_metric", EnumerationValue(["power", "absum"], default="power"),
            group=G, tooltip="'power' = |I|^2+|Q|^2 ; 'absum' = |I|+|Q|")

        # -- how the threshold sits above the measured background --
        self.setattr_argument(
            "rfsoc_margin_db",
            NumberValue(default=3.0, unit="dB", scale=1, ndecimals=1, step=0.5),
            group=G, tooltip="v_thresh = background level x (+margin dB)")
        self.setattr_argument(
            "rfsoc_bg_percentile", StringValue("max"), group=G,
            tooltip="background reference level: 'max' (margin dB above the largest "
                    "background sample) or a percentile like '99.9'")
        self.setattr_argument(
            "rfsoc_bg_seconds",
            NumberValue(default=2.0, unit="s", scale=1, ndecimals=1, step=0.5),
            group=G, tooltip="how long the RFSoC samples the background")

        self.setattr_argument(
            "rfsoc_run_apparatus_hooks", BooleanValue(default=True), group=G,
            tooltip="call rfsoc_calib_setup() / rfsoc_calib_teardown() around the "
                    "measurement (override them in a subclass to set the apparatus "
                    "into the detection state, minus the signal)")

    # -- apparatus-state hooks: empty here; override in a subclass --------- #
    def rfsoc_calib_setup(self):
        V_on = self.FET_V_nominal
        # V_off = V_on - self.V_off_change
        self.FEtip_PSU.ramp_up_ch(self.FET_ch_fixed, self.FET_V_fixed)
        self.FEtip_PSU.select_ch(self.FET_ch_sweep)
        self.FEtip_PSU.ramp_up(V_on)
        self.Valon.output_on() 
        self.Valon.set_power(self.P_load)


    def rfsoc_calib_teardown(self):
        self.FEtip_PSU.ramp_down(0)
        self.FEtip_PSU.ramp_down_ch(self.FET_ch_fixed, 0)
        self.Valon.output_off()

    # ------------------------------------------------------------------ #
    def rfsoc_config(self) -> dict:
        """The (pulse-less) StandbyConfig dict handed to ``qick_standby calibrate``."""
        try:
            bgp = float(self.rfsoc_bg_percentile)
        except ValueError:
            bgp = self.rfsoc_bg_percentile          # "max"
        return dict(
            dac_pulse=1, adc_wait=0, adc_record=-1,
            read_freq=float(self.rfsoc_read_freq),
            record_freq=float(self.rfsoc_read_freq),
            pulse_freq=float(self.rfsoc_read_freq),
            pulse_voltage=0.0,                       # never drive during calibration
            readout_length=int(self.rfsoc_readout_length),
            metric=str(self.rfsoc_metric),
            v_thresh="auto",
            threshold_margin_db=float(self.rfsoc_margin_db),
            bg_percentile=bgp,
            bg_seconds=float(self.rfsoc_bg_seconds),
        )

    def prepare(self):
        FeedbackExperiments.prepare(self)
        self._R = _load_rfsoc_client(self.rfsoc_host)


    def run(self):
        R = self._R
        tag = str(self.rfsoc_calib_tag).strip() or "shared"
        sid = "rfsoc_calib_%s" % tag
        cfg = self.rfsoc_config()

        print("[rfsoc-calib] measuring background on %s  (signal OFF, %.1f s, ref=%s)"
              % (self.rfsoc_host, cfg["bg_seconds"], cfg["bg_percentile"]))
        if self.rfsoc_run_apparatus_hooks:
            self.rfsoc_calib_setup()
        try:
            cal = R.calibrate(cfg, sid, margin_db=cfg["threshold_margin_db"],
                              bg_seconds=cfg["bg_seconds"], write_config=True)
        finally:
            if self.rfsoc_run_apparatus_hooks:
                self.rfsoc_calib_teardown()

        vth = cal.get("v_thresh")
        if vth is None:
            raise RuntimeError("RFSoC calibration returned no v_thresh: %r" % cal)
        print("[rfsoc-calib] v_thresh = %s   (bg_level %s, +%s dB, %s samples, %s)"
              % (vth, cal.get("bg_level"), cal.get("threshold_margin_db"),
                 cal.get("n_samples"), cal.get("db_convention")))

        rec = dict(cal, tag=tag, sid=sid, host=str(self.rfsoc_host),
                   read_freq=cfg["read_freq"], readout_length=cfg["readout_length"],
                   metric=cfg["metric"], t_wall=time.time(),
                   iso=time.strftime("%Y-%m-%dT%H:%M:%S"))

        # tagged, persistent -- FeedbackWithRFSoC(rfsoc_use_external_calib=True,
        # rfsoc_calib_tag=<tag>) reads these
        self.set_dataset("rfsoc_calib_%s_v_thresh" % tag, vth,
                         broadcast=True, persist=True)
        self.set_dataset("rfsoc_calib_%s_read_freq" % tag, cfg["read_freq"],
                         broadcast=True, persist=True)
        self.set_dataset("rfsoc_calib_%s_readout_length" % tag, cfg["readout_length"],
                         broadcast=True, persist=True)
        self.set_dataset("rfsoc_calib_%s_metric" % tag, cfg["metric"],
                         broadcast=True, persist=True)
        self.set_dataset("rfsoc_calib_%s" % tag, json.dumps(rec),
                         broadcast=True, persist=True)
        # "latest" pointers
        self.set_dataset("rfsoc_calib_latest_tag", tag, broadcast=True, persist=True)
        self.set_dataset("rfsoc_v_thresh", vth, broadcast=True, persist=True)
        self.set_dataset("rfsoc_calibration", json.dumps(rec), broadcast=True, persist=True)

        # a local copy next to the ARTIQ results, independent of the master DB
        try:
            with open("rfsoc_calib_%s.json" % tag, "w") as f:
                json.dump(rec, f, indent=2)
        except OSError as e:
            print("[rfsoc-calib] could not write local json:", repr(e))

        print("[rfsoc-calib] stored under tag %r "
              "(board: standby_out/%s/calibration.json)" % (tag, sid))
