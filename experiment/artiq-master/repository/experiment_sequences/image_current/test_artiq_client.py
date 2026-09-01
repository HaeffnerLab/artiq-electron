#!/usr/bin/env python3
"""
test_artiq_client.py  --  end-to-end test of the ARTIQ-host RFSoC standby client
===============================================================================

This is the ARTIQ-side analogue of ``test/test_standby_full.py``.  That test
drives ``StandbySupervisor`` directly ON THE BOARD; this one drives the
fire-and-forget host client (``artiq_rfsoc_standby.py``) the exact way
``feedback_experiments_rfsoc.FeedbackWithRFSoC`` does from an ARTIQ experiment's
``prepare()`` / ``run()`` / ``analyze()``::

    calibrate()  ->  submit()  ->  poll() / read_jsonl() / latest_event()
                 ->  stop()  ->  fetch()

Run it FROM THE ARTIQ HOST (or any machine with ``ssh rfsoc`` + ``scp``)::

    python jupyter_notebooks/Feedback-drive/test/test_artiq_client.py

Wiring on the board (TEST MODE -- loopback):

    DAC 0  ->  ADC 0     detection input; DDR4 records THIS channel (adc_record=-1)
    DAC 1  ->  ADC 1     feedback pulse output (gen 1)

A periodic fake signal is injected on gen 0 (``cfg.stim_*``) so a threshold
crossing is guaranteed without any external source -- the same fixture the board
test uses.  The DDR4 window records ADC0 (the injected signal), the MR fallback
snapshots the revival crossings, ADC1 just shows the pulse fired.

Environment:

    RFSOC_HOST    ssh alias / host for the board          (default "rfsoc")
    RFSOC_STANDBY_ROOT   remote Feedback-drive path  (default the board default)
    SKIP_SSH=1    run only the offline checks (pulse_designer / config plumbing)

The offline checks need nothing but this repo.  The ssh checks need the board
reachable and FREE (no other ``QickSoc()`` holding the PL); they leave a
``standby_out/artiqtest_*`` session dir on the board and fetch it locally.

A JSON summary is written to ``test/results_artiq_client.json``; exit code is 0
only if nothing FAILED.
"""
import json
import os
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
FBDIR = os.path.dirname(HERE)                       # jupyter_notebooks/Feedback-drive
REPO = os.path.dirname(os.path.dirname(FBDIR))      # repo root (has feedback_experiments_rfsoc.py)
sys.path.insert(0, FBDIR)

import pulse_designer as PD          # noqa: E402
import artiq_rfsoc_standby as R      # noqa: E402

RESULTS = []


def record(name, ok, msg=""):
    tag = "PASS" if ok is True else ("SKIP" if ok is None else "FAIL")
    print(f"  [{tag}] {name}: {msg}")
    RESULTS.append({"test": name, "result": tag, "msg": msg})


# --------------------------------------------------------------------------- #
#  offline: pulse_designer exact-number API + the config plumbing ARTIQ uses
# --------------------------------------------------------------------------- #
def test_exact_numbers():
    """make_spec() must store carrier frequency and timing verbatim."""
    f = 300.123456789
    s = PD.make_spec(freq_mhz=f, initial_delay_us=999.9990001, on_us=1000.5,
                     off_us=3000.25, repeats=3.0, ramp_us=49.999, shape="trapezoid")
    ok = (s.freq_mhz == f and s.on_us == 1000.5 and s.off_us == 3000.25
          and s.initial_delay_us == 999.9990001
          and s.repeats == 3 and isinstance(s.repeats, int))
    record("make_spec_keeps_exact_values", ok,
           f"freq={s.freq_mhz!r} on={s.on_us!r} delay={s.initial_delay_us!r} "
           f"repeats={s.repeats!r}")


def test_design_roundtrip(tmp):
    """design() writes a standby config whose pulse_* block is exact."""
    p = os.path.join(tmp, "exact.json")
    f = 287.654321
    PD.design(p, None, verbose=False, freq_mhz=f, on_us=1234.5, off_us=678.0,
              initial_delay_us=42.125, repeats=2, shape="ramp_up", ramp_us=10.0)
    cfg = json.load(open(p))
    ok = (cfg["pulse_freq"] == f and cfg["pulse_on_us"] == 1234.5
          and cfg["pulse_initial_delay_us"] == 42.125
          and cfg["pulse_length_us"] == 1234.5 and cfg["pulse_shape"] == "ramp_up")
    record("design_writes_exact_config", ok,
           f"pulse_freq={cfg['pulse_freq']!r} pulse_on_us={cfg['pulse_on_us']!r}")


def test_pulse_config_override(tmp):
    """Emulate FeedbackWithRFSoC.rfsoc_config(): a pulse_designer JSON overrides
    the pulse_* fields of the base standby config, carrier frequency included."""
    pj = os.path.join(tmp, "designed.json")
    PD.design(pj, None, verbose=False, freq_mhz=123.4567, on_us=500.0, repeats=4)
    base = dict(dac_pulse=1, adc_wait=0, adc_record=-1, read_freq=25.0,
                pulse_freq=300.0, pulse_voltage=0.0, pulse_length_us=2000.0)
    for k, v in json.load(open(pj)).items():
        if k.startswith("pulse_"):
            base[k] = v
    ok = base["pulse_freq"] == 123.4567 and base["pulse_repeats"] == 4
    record("pulse_designer_json_overrides_config", ok,
           f"merged pulse_freq={base['pulse_freq']!r} repeats={base['pulse_repeats']}")


def test_artiq_module_imports():
    """feedback_experiments_rfsoc needs artiq + the parent experiment module; if
    they are not on this host just note it -- the host client is what we test."""
    sys.path.insert(0, REPO)
    try:
        import feedback_experiments_rfsoc as FX
    except Exception as e:
        record("feedback_experiments_rfsoc_import", None,
               f"not importable on this host ({e!r}) -- ARTIQ side untested here")
        return
    C = FX.FeedbackWithRFSoC
    ok = all(hasattr(C, m) for m in
             ("rfsoc_config", "rfsoc_calibrate_and_start",
              "rfsoc_calib_setup", "rfsoc_calib_teardown", "rfsoc_stop_and_fetch"))
    record("feedback_experiments_rfsoc_import", ok, "FeedbackWithRFSoC API present")


# --------------------------------------------------------------------------- #
#  ssh: the real fire-and-forget lifecycle against the board (loopback)
# --------------------------------------------------------------------------- #
STIM_CFG = dict(
    dac_pulse=1, adc_wait=0, adc_record=-1,
    read_freq=300.0, record_freq=300.0, pulse_freq=300.0,
    pulse_voltage=0.9, readout_length=300, metric="absum",
    v_thresh=1500, window_us=2600.0,
    edge_detect=True, edge_rearm_frac=0.55,
    pulse_blocking=False, mr_fallback=True, pulse_when_disarmed=False,
    pulse_on_us=400.0, pulse_off_us=200.0, pulse_repeats=2,
    pulse_initial_delay_us=60.0,
    stim_ch=0, stim_on_us=60.0, stim_period_us=300.0, stim_gain=0.6,
    stim_start_us=150.0, stim_max_bursts=5,
    # long backstop: on a board where `bash -lc` (hence every ssh round-trip) is
    # slow, submit()+the first polls can take a minute, so keep the session alive
    # well past that -- stop() in the finally does the actual stopping.
    max_events=0, max_seconds=240.0, calib_seconds=0.3, poll_interval_s=0.004,
)


def ssh_ok():
    try:
        return R._ssh("echo ok", login=False).strip() == "ok"
    except Exception:
        return False


def test_ssh_session(tmp):
    sid = time.strftime("artiqtest_%Y%m%d_%H%M%S")

    # 1) calibrate (in a real run the signal is OFF here) -> numeric v_thresh,
    #    written into the remote config.json (mirrors rfsoc_calibrate_and_start).
    cal_cfg = {k: v for k, v in STIM_CFG.items() if not k.startswith("stim_")}
    cal_cfg.update(v_thresh="auto", pulse_voltage=0.0,
                   bg_seconds=0.4, bg_percentile="max", threshold_margin_db=6.0)
    try:
        cal = R.calibrate(cal_cfg, sid, margin_db=6.0, bg_seconds=0.4,
                          write_config=True)
        vth = cal.get("v_thresh")
        record("client_calibrate", isinstance(vth, (int, float)) and vth > 0,
               f"v_thresh={vth}  bg_level={cal.get('bg_level')}")
        # a different process reads the number back (standalone-calib workflow)
        back = R.get_calibration(sid)
        record("client_get_calibration", back.get("v_thresh") == vth,
               f"calibration.json v_thresh={back.get('v_thresh')} (== {vth})")
    except Exception as e:
        record("client_calibrate", False, f"{e!r}")
        record("client_get_calibration", None, "calibrate step failed")

    # 2) submit the stim run (fire-and-forget)
    try:
        got = R.submit(STIM_CFG, sid)
        record("client_submit", got == sid, f"sid={got}")
    except Exception as e:
        record("client_submit", False, f"{e!r}")
        return

    try:
        # 3) poll until an event lands: stim burst 1 -> crossing -> DDR4 capture.
        #    Every poll is an ssh round-trip under `bash -lc` -- on this board
        #    that is ~10-15 s, so the session may already be running (or even
        #    finished) by the first poll.  The "alive" signal is a well-formed
        #    status with a known state, not a particular transient one; the
        #    stim-injected crossing guarantees events>=1 regardless of timing.
        LIVE = {"configured", "calibrating", "running", "stopped"}
        ev, states, hb, t0 = 0, set(), 0, time.time()
        while time.time() - t0 < 60:
            st = R.poll(sid)
            states.add(st.get("state"))
            ev = max(ev, int(st.get("events") or 0))
            hb = max(hb, int(st.get("heartbeat") or 0))
            if ev >= 1:
                break
            time.sleep(1.0)
        record("client_poll_status", bool(states & LIVE) or ev >= 1 or hb > 0,
               f"states seen={sorted(s for s in states if s)}  heartbeat={hb}  events={ev}")
        record("client_detects_event", ev >= 1,
               f"events={ev} after {time.time() - t0:.0f}s (stim-injected crossing)")

        # 4) crossings.jsonl + manifest.jsonl readable and non-empty
        cr = R.read_jsonl(sid, "crossings.jsonl", tail=200)
        man = R.read_jsonl(sid, "manifest.jsonl")
        caps = sorted({m.get("capture") for m in man})
        record("client_read_jsonl", len(cr) >= 1 and len(man) >= 1,
               f"{len(cr)} crossings, {len(man)} manifest rows, captures={caps}")

        # 5) latest_event downloads the newest event_*.npz and decodes it
        t, mag, meta = R.latest_event(sid, os.path.join(tmp, "live"), n_points=1500)
        n = 0 if t is None else len(t)
        record("client_latest_event", t is not None and n > 100 and n == len(mag),
               f"{n} envelope points, npz={meta.get('npz')}")
    finally:
        # 6) stop -> confirmed, heartbeat frozen, event count preserved
        st = R.stop(sid, timeout=30)
    record("client_stop", st.get("state") == "stopped" and int(st.get("events") or 0) >= 1,
           f"state={st.get('state')} events={st.get('events')} missed={st.get('missed')}")

    # 7) fetch(full=False) -> JSON summaries only, no per-event npz
    dlight = os.path.join(tmp, "fetch_light")
    R.fetch(sid, dlight, full=False)
    light_ok = all(os.path.exists(os.path.join(dlight, f))
                   for f in ("status.json", "manifest.jsonl"))
    n_light = len([f for f in os.listdir(dlight)
                   if f.startswith("event_") and f.endswith(".npz")])
    record("client_fetch_light", light_ok and n_light == 0,
           f"status+manifest present, {n_light} event npz (expect 0)")

    # 8) fetch(full=True) -> at least one event_*.npz
    dfull = os.path.join(tmp, "fetch_full")
    R.fetch(sid, dfull, full=True)
    n_full = len([f for f in os.listdir(dfull)
                  if f.startswith("event_") and f.endswith(".npz")])
    record("client_fetch_full", n_full >= 1, f"{n_full} event npz fetched to {dfull}")


# --------------------------------------------------------------------------- #
def main():
    print("=== ARTIQ RFSoC standby client test ===")
    tmp = tempfile.mkdtemp(prefix="artiq_rfsoc_test_")
    print(f"scratch: {tmp}\nboard:   {R.RFSOC_HOST}")

    test_exact_numbers()
    test_design_roundtrip(tmp)
    test_pulse_config_override(tmp)
    test_artiq_module_imports()

    if os.environ.get("SKIP_SSH") == "1":
        record("ssh_session", None, "SKIP_SSH=1 -- offline checks only")
    elif not ssh_ok():
        record("ssh_session", None, f"no ssh to {R.RFSOC_HOST!r} -- ssh checks skipped")
    else:
        try:
            test_ssh_session(tmp)
        except Exception as e:
            record("ssh_session", False, f"EXCEPTION {e!r}")
            traceback.print_exc()

    n_fail = sum(1 for r in RESULTS if r["result"] == "FAIL")
    n_pass = sum(1 for r in RESULTS if r["result"] == "PASS")
    n_skip = sum(1 for r in RESULTS if r["result"] == "SKIP")
    print(f"\n==== {n_pass} passed, {n_fail} failed, {n_skip} skipped ====")
    with open(os.path.join(HERE, "results_artiq_client.json"), "w") as f:
        json.dump({"pass": n_pass, "fail": n_fail, "skip": n_skip, "tests": RESULTS},
                  f, indent=2)
    return n_fail


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
