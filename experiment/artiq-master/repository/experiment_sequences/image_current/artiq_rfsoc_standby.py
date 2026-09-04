"""
artiq_rfsoc_standby.py
======================

Thin host-side client for firing a fire-and-forget QICK "standby detector" session
on the RFSoC and collecting its results later. Pure stdlib + ssh/rsync; **no ARTIQ
kernel code** - call these from an ARTIQ experiment's host methods (`prepare`,
`run`, `analyze`) or from any plain Python.

Model:
  - `submit(config)`  writes the config to the RFSoC and launches
                      `python -m qick_standby run` under nohup; returns a session id.
  - `poll(session_id)` runs `qick_standby status` over ssh (no hardware touched).
  - `stop(session_id)` runs `qick_standby stop` over ssh.
  - `fetch(session_id, dest)` rsyncs the session output directory locally.

Assumes an ssh host alias ``rfsoc`` (see ~/.ssh/config) with key auth.

Example (ARTIQ host code)::

    from artiq_rfsoc_standby import submit, poll, stop, fetch

    class MyExperiment(EnvExperiment):
        def prepare(self):
            self.sid = submit({
                "dac_pulse": 1, "adc_wait": 0, "read_freq": 25, "pulse_freq": 300,
                "pulse_voltage": 0.5, "pulse_length_us": 2000.0,
                "readout_length": 300, "v_thresh": 50000, "window_us": 2400.0,
                "max_events": 100, "max_seconds": 3600,
            })

        def run(self):
            # ... do ARTIQ things ...
            print(poll(self.sid))

        def analyze(self):
            stop(self.sid)
            fetch(self.sid, "/data/rfsoc/%s" % self.sid)
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time

RFSOC_HOST = os.environ.get("RFSOC_HOST", "rfsoc")
# non-hardware commands (status / stop) - just need the venv python
REMOTE_PY = os.environ.get("RFSOC_PY", "python3")
# hardware commands (run / calibrate) construct QickSoc() -> need root.
# The board has a passwordless-sudo rule for exactly this binary; override the whole
# string for a different setup (e.g. a root-owned runner).
REMOTE_PY_HW = os.environ.get(
    "RFSOC_PY_HW", "sudo -n /usr/local/share/pynq-venv/bin/python3")
REMOTE_ROOT = os.environ.get("RFSOC_STANDBY_ROOT",
                             "/home/xilinx/jupyter_notebooks/Feedback-drive")
_SSH_OPTS = ["-o", "BatchMode=yes"]


def _ssh(cmd: str, input_text: str | None = None, check: bool = True,
         login: bool = True) -> str:
    """Run ``cmd`` on the RFSoC. With ``login`` (default) it runs under
    ``bash -lc`` so /etc/profile.d sets BOARD, activates the pynq venv, and
    sets XILINX_XRT - required for anything that imports ``qick``."""
    remote = f"bash -lc {shlex.quote(cmd)}" if login else cmd
    proc = subprocess.run(
        ["ssh", *_SSH_OPTS, RFSOC_HOST, remote],
        input=input_text, capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"ssh `{cmd}` failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def _remote_session_dir(session_id: str) -> str:
    return f"{REMOTE_ROOT}/standby_out/{session_id}"


def submit(config: dict | None, session_id: str | None = None) -> str:
    """Launch a standby session on the RFSoC. Returns the session id.
    ``config=None`` reuses the config already on the RFSoC (e.g. the one
    ``calibrate(..., write_config=True)`` just wrote) instead of overwriting it."""
    sid = session_id or time.strftime("standby_%Y%m%d_%H%M%S")
    rdir = _remote_session_dir(sid)
    _ssh(f"mkdir -p {shlex.quote(rdir)}")
    if config is not None:
        _ssh(f"cat > {shlex.quote(rdir + '/config.json')}",
             input_text=json.dumps(config, indent=2))
    # `--daemonize` makes `qick_standby run` double-fork before it touches the
    # board, so this call returns as soon as the session has detached instead of
    # blocking for the session's whole lifetime. That matters here because the
    # board's sudoers sets `use_pty`: `sudo` keeps a pty relay alive for its
    # command and that relay holds the ssh channel open, so `nohup ... &` alone
    # never returns. The daemon writes its real pid to <rdir>/launch.pid and its
    # stdio to <rdir>/nohup.out.
    launch = (
        f"cd {shlex.quote(REMOTE_ROOT)} && "
        f"{REMOTE_PY_HW} -m qick_standby run "
        f"--config {shlex.quote(rdir + '/config.json')} "
        f"--outdir {shlex.quote(rdir)} --daemonize"
    )
    _ssh(launch)
    return sid


def calibrate(config: dict, session_id: str | None = None,
              margin_db: float | None = None, bg_seconds: float | None = None,
              write_config: bool = True) -> dict:
    """Measure the background and set v_thresh. Run this with the **signal OFF**
    (ARTIQ: everything on except the signal). Returns the calibration dict; with
    write_config=True the numeric v_thresh is written into the remote config so a
    later submit() of the same session_id uses it."""
    sid = session_id or time.strftime("standby_%Y%m%d_%H%M%S")
    rdir = _remote_session_dir(sid)
    _ssh(f"mkdir -p {shlex.quote(rdir)}")
    _ssh(f"cat > {shlex.quote(rdir + '/config.json')}",
         input_text=json.dumps(config, indent=2))
    cmd = (f"cd {shlex.quote(REMOTE_ROOT)} && {REMOTE_PY_HW} -m qick_standby "
           f"calibrate --config {shlex.quote(rdir + '/config.json')} "
           f"--outdir {shlex.quote(rdir)}")
    if margin_db is not None:
        cmd += f" --margin-db {margin_db}"
    if bg_seconds is not None:
        cmd += f" --bg-seconds {bg_seconds}"
    if write_config:
        cmd += " --write-config"
    out = _ssh(cmd)
    try:
        return json.loads(out[out.index("{"):out.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {"raw": out.strip()}


def get_calibration(session_id: str) -> dict:
    """Return the ``calibration.json`` a previous :func:`calibrate` wrote for
    this session id (``{}`` if there is none). Lets a *different* process (e.g. a
    later feedback run, or a standalone calibration experiment) read the number
    back off the board."""
    rf = f"{_remote_session_dir(session_id)}/calibration.json"
    out = _ssh(f"cat {shlex.quote(rf)} 2>/dev/null || true", login=False)
    try:
        return json.loads(out)
    except (ValueError, json.JSONDecodeError):
        return {}


def poll(session_id: str) -> dict:
    """Return the session's status.json as a dict (raises if unreachable)."""
    out = _ssh(
        f"cd {shlex.quote(REMOTE_ROOT)} && {shlex.quote(REMOTE_PY)} -m qick_standby "
        f"status --outdir {shlex.quote('standby_out/' + session_id)}",
        check=False,
    )
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"state": "unknown", "raw": out.strip()}


def is_running(session_id: str) -> bool:
    return poll(session_id).get("state") in ("running", "configured")


# --------------------------------------------------------------------------- #
#  lightweight readers for a live applet - file reads only, never touch the tProc
# --------------------------------------------------------------------------- #
def read_jsonl(session_id: str, name: str, tail: int | None = None) -> list:
    """Read a *.jsonl file (manifest / crossings) from the session dir. ``tail``
    limits to the last N lines (cheap: uses `tail` on the board)."""
    rf = f"{_remote_session_dir(session_id)}/{name}"
    cmd = (f"tail -n {int(tail)} {shlex.quote(rf)}" if tail
           else f"cat {shlex.quote(rf)}")
    out = _ssh(cmd + " 2>/dev/null || true", login=False)
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


# 4x2 decimated DDR4 readout rate [MHz]; an MR snapshot carries its own fs in the npz
F_OUT_MHZ = float(os.environ.get("RFSOC_F_OUTPUT_MHZ", "552.96"))


def _manifest_is_mr(row: dict) -> bool:
    return (str(row.get("npz", "")).startswith("event_mr")
            or row.get("capture") == "mr_snapshot")


def _last_capture(session_id: str, kind: str):
    """Newest manifest row of ``kind`` ("ddr4" | "mr" | "any"), filtered on the
    board so we never `cat` the whole (large) manifest."""
    rf = f"{_remote_session_dir(session_id)}/manifest.jsonl"
    if kind == "ddr4":
        cmd = f"grep -v mr_snapshot {shlex.quote(rf)} | tail -n 1"
    elif kind == "mr":
        cmd = f"grep mr_snapshot {shlex.quote(rf)} | tail -n 1"
    else:
        cmd = f"tail -n 1 {shlex.quote(rf)}"
    out = _ssh(cmd + " 2>/dev/null || true", login=False).strip()
    try:
        return json.loads(out) if out else None
    except json.JSONDecodeError:
        return None


def envelope_decimate(mag, t, n_points: int):
    """Per-bin min / max / mean downsample of a waveform for display: the
    min/max band keeps narrow spikes that plain striding would drop, the mean
    tracks the signal level. Returns ``(t_bins, lo, hi, mean)``, each length
    <= n_points."""
    import numpy as np
    mag = np.asarray(mag); t = np.asarray(t)
    if len(mag) <= 2 * n_points:
        return t, mag, mag, mag
    s = int(np.ceil(len(mag) / n_points))
    k = (len(mag) // s) * s
    m = mag[:k].reshape(-1, s)
    return t[:k:s], m.min(1), m.max(1), m.mean(1)


def latest_event(session_id: str, dest: str, n_points: int = 2000, kind: str = "ddr4"):
    """Download the newest capture of ``kind`` and return
    ``(t_us, mag_hi, meta)`` where ``mag_hi`` is the per-bin **peak** of the
    magnitude ``sqrt(I^2+Q^2)`` envelope-decimated to <= n_points points, and
    ``meta`` also carries ``mag_lo`` (per-bin min), ``mag_mean`` (per-bin mean),
    ``fs_mhz``, ``n_raw``, ``local`` (the downloaded path). ``(None, None, {})``
    if there is no such capture yet.

    kind: ``"ddr4"`` (default) = the full ~2 ms DDR4 window (what you almost
    always want); ``"mr"`` = the short MR-buffer fallback snapshot; ``"any"`` =
    whichever capture is newest in the manifest.
    """
    import numpy as np
    ev = _last_capture(session_id, kind)
    if not ev:
        return None, None, {}
    os.makedirs(dest, exist_ok=True)
    local = os.path.join(dest, ev["npz"])
    if not os.path.exists(local):                       # cache: npz never changes
        subprocess.run(["scp", *_SSH_OPTS,
                        f"{RFSOC_HOST}:{_remote_session_dir(session_id)}/{ev['npz']}", local],
                       check=True)
    d = np.load(local)
    iq = d["iq"].astype(np.float32)
    mag = np.hypot(iq[:, 0], iq[:, 1])
    fs_mhz = float(d["fs_msps"]) if "fs_msps" in getattr(d, "files", []) else F_OUT_MHZ
    t = np.arange(len(mag)) / fs_mhz                    # microseconds
    tb, lo, hi, mean = envelope_decimate(mag, t, int(n_points))
    meta = dict(ev, fs_mhz=fs_mhz, n_raw=int(len(mag)), local=local,
                mag_lo=lo, mag_mean=mean, t_us=tb)
    return tb, hi, meta


def stop(session_id: str, timeout: float = 30.0, force: bool = False) -> dict:
    """Request a clean stop and wait for confirmation. ``force=True`` adds
    ``--force``: if the session does not confirm (its supervisor process was
    hard-killed) the board is attached and the tProc halted directly - needs
    the venv python (sudo) so it uses REMOTE_PY_HW."""
    py = REMOTE_PY_HW if force else REMOTE_PY
    _ssh(
        f"cd {shlex.quote(REMOTE_ROOT)} && {py} -m qick_standby "
        f"stop --outdir {shlex.quote('standby_out/' + session_id)} "
        f"--timeout {timeout}{' --force' if force else ''}",
        check=False,
    )
    return poll(session_id)


def list_sessions() -> list:
    """Every standby session dir on the board, each ``{sid, outdir, state,
    supervisor_pid, stuck}``. ``stuck`` = still running / has a live supervisor.
    No hardware touched."""
    out = _ssh(
        f"cd {shlex.quote(REMOTE_ROOT)} && {shlex.quote(REMOTE_PY)} -m qick_standby sessions",
        check=False,
    )
    try:
        return json.loads(out[out.index("{"):out.rindex("}") + 1]).get("sessions", [])
    except (ValueError, json.JSONDecodeError):
        return []


def cleanup(exclude=None, timeout: float = 20.0, force: bool = True) -> list:
    """Stop every standby session on the board that is still running (or has a
    live supervisor), EXCEPT any session id in ``exclude``. Returns the list of
    sessions that were stopped (``[]`` if the board was already clean).

    Call this right before :func:`submit` so a previous run that was hard-killed
    on the ARTIQ side (its ``analyze``/``finally`` never ran) does not keep the
    board busy - no manual ``qick_standby stop`` needed. ``force=True`` also
    halts the tProc for a session whose supervisor process is gone."""
    if exclude is None:
        ex = []
    elif isinstance(exclude, (list, tuple, set)):
        ex = list(exclude)
    else:
        ex = [exclude]
    flags = "".join(f" --exclude {shlex.quote(str(e))}" for e in ex)
    py = REMOTE_PY_HW if force else REMOTE_PY
    out = _ssh(
        f"cd {shlex.quote(REMOTE_ROOT)} && {py} -m qick_standby cleanup "
        f"--timeout {timeout}{' --force' if force else ''}{flags}",
        check=False,
    )
    try:
        return json.loads(out[out.index("{"):out.rindex("}") + 1]).get("cleaned", [])
    except (ValueError, json.JSONDecodeError):
        return []


def _have(prog: str) -> bool:
    import shutil
    return shutil.which(prog) is not None


def fetch(session_id: str, dest: str, full: bool = True) -> str:
    """Copy the remote session directory into ``dest``. Returns ``dest``.
    With ``full=False`` the (large) per-event ``event_*.npz`` are skipped - you
    still get manifest.jsonl / crossings.jsonl / status.json / calibration.json.
    Uses rsync when available, else falls back to scp."""
    os.makedirs(dest, exist_ok=True)
    rdir = _remote_session_dir(session_id)
    if _have("rsync"):
        cmd = ["rsync", "-az"]
        if not full:
            cmd += ["--exclude", "event_*.npz"]
        cmd += [f"{RFSOC_HOST}:{rdir}/", dest.rstrip("/") + "/"]
        subprocess.run(cmd, check=True)
    elif full:
        subprocess.run(["scp", "-r", *_SSH_OPTS,
                        f"{RFSOC_HOST}:{rdir}/.", dest], check=True)
    else:
        names = _ssh(f"cd {shlex.quote(rdir)} && ls | grep -v '^event_.*\\.npz$' || true",
                     login=False).split()
        for n in names:
            subprocess.run(["scp", *_SSH_OPTS, f"{RFSOC_HOST}:{rdir}/{n}",
                            os.path.join(dest, n)], check=False)
    return dest


def purge_remote(session_id: str, dest: str) -> int:
    """Delete the remote session directory - but ONLY after verifying every
    file that exists on the board also exists in ``dest`` (the local copy a
    prior :func:`fetch` produced) with a matching size. Raises ``RuntimeError``
    instead of deleting anything if that check fails, so a partial/failed
    fetch can never cost you the only copy of the data. Returns the number of
    remote files verified and removed."""
    rdir = _remote_session_dir(session_id)
    out = _ssh(f"cd {shlex.quote(rdir)} && find . -type f -printf '%P %s\\n'",
               login=False)
    remote_files = {}
    for line in out.splitlines():
        line = line.strip("\n")
        if not line:
            continue
        name, _, size = line.rpartition(" ")
        remote_files[name] = int(size)

    if not remote_files:
        raise RuntimeError(f"remote session dir {rdir} listed no files "
                            f"(nothing to verify) -- refusing to purge")

    for name, size in remote_files.items():
        local_path = os.path.join(dest, name)
        if not os.path.isfile(local_path):
            raise RuntimeError(f"local copy is missing {name!r} -- refusing to purge {rdir}")
        local_size = os.path.getsize(local_path)
        if local_size != size:
            raise RuntimeError(f"size mismatch for {name!r} (remote {size}, local "
                                f"{local_size}) -- refusing to purge {rdir}")

    _ssh(f"rm -rf {shlex.quote(rdir)}", login=False)
    return len(remote_files)


def wait(session_id: str, poll_interval: float = 10.0, timeout: float | None = None) -> dict:
    """Block until the session reports 'stopped' (or 'error'), or timeout."""
    t0 = time.time()
    while True:
        st = poll(session_id)
        if st.get("state") in ("stopped", "error", "unknown"):
            return st
        if timeout is not None and time.time() - t0 > timeout:
            return st
        time.sleep(poll_interval)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="RFSoC standby client")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit"); s.add_argument("config"); s.add_argument("--sid")
    s = sub.add_parser("calibrate"); s.add_argument("config"); s.add_argument("--sid")
    s.add_argument("--margin-db", type=float, dest="margin_db")
    s = sub.add_parser("poll"); s.add_argument("sid")
    s = sub.add_parser("stop"); s.add_argument("sid")
    s = sub.add_parser("fetch"); s.add_argument("sid"); s.add_argument("dest")
    a = ap.parse_args()
    if a.cmd == "submit":
        with open(a.config) as f:
            print(submit(json.load(f), a.sid))
    elif a.cmd == "calibrate":
        with open(a.config) as f:
            print(json.dumps(calibrate(json.load(f), a.sid,
                                       margin_db=getattr(a, "margin_db", None)), indent=2))
    elif a.cmd == "poll":
        print(json.dumps(poll(a.sid), indent=2))
    elif a.cmd == "stop":
        print(json.dumps(stop(a.sid), indent=2))
    elif a.cmd == "fetch":
        print(fetch(a.sid, a.dest))
