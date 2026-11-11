#!/usr/bin/env python3
"""Deterministic duplicate/recurrence checker for macOS .ips evidence.

Decides by fixed rules whether a new crash report is already recorded in
this repository. No AI, no network, stdlib only: same input -> same answer.

Fingerprint per evidence file (all fields from the .ips JSON body):
  - app bundle CFBundleIdentifier
  - app binary build UUID (usedImage whose bundle id matches; pins the build)
  - exception kind: type + signal + subtype (addresses normalized to 0xADDR)
    + address class: near-null (< 0x100000) vs wild
  - top-3 imageOffsets of app-side frames on the faulting thread, in stack
    order (stable across runs within one build; ASLR only shifts load bases)
  - dispatch queue of the faulting thread

Raw fault addresses are NEVER compared directly (ASLR changes every run).

Pairwise rules (evidence from different issue directories):
  bundle differs                        -> SKIP  (irrelevant pair)
  same bundle, different exception kind -> SKIP  (different bug in same app)
  same build + kind + queue + top-3 app-frame offsets all match
                                        -> T1 RECURRENCE
  same build + kind, offsets differ     -> T2 POSSIBLE (review)
  different build + same kind + queue   -> T2 POSSIBLE (offsets may shift)
  anything else same-app                -> INFO (same app, different shape)

Exit codes: 0 clean | 10 at least one T1 | 11 only T2 |
            3 unparsable input | 2 usage

Usage:
  check_duplicates.py <new-report.ips>      # compare one report vs all issues
  check_duplicates.py --scan-all            # pairwise cross-check of the repo
  check_duplicates.py <file.ips> --verbose  # also dump extracted signatures
  check_duplicates.py <file.ips> --repo DIR # compare against another checkout
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

PLATFORM_DIRS = ("macos", "android")
NEAR_NULL_LIMIT = 0x100000   # below 1 MiB: classic null/near-null dereference
PREFIX_FRAMES = 3            # app-side frames that pin the code path

T_SKIP, T_INFO, T2, T1 = 0, 1, 2, 3   # ordered by match strength
LABEL = {T_SKIP: "SKIP", T_INFO: "INFO", T2: "POSSIBLE", T1: "RECURRENCE"}

ACTION_RECURRENCE = """  action : record in the EXISTING issue, do NOT scaffold a new one:
           1. sanitize the new .ips (README: Security and privacy) into that issue's evidence/
           2. append a row to its report.md "## Recurrences" (date, fp, incident id, filename)
           3. update the README index note (recurrence count / last seen)"""

ACTION_POSSIBLE = """  action : human review before deciding:
           - build changed -> re-check with `atos -o <binary> -l <load> <offsets>`
           - same symptom  -> treat as recurrence (see steps under T1)
           - different     -> open a new issue normally"""


class ParseError(ValueError):
    pass


def parse_ips(text: str):
    """Return (metadata-line-obj, crash-body-obj) from .ips text."""
    dec = json.JSONDecoder()
    meta: dict | None = None
    body: dict | None = None
    # A .ips can embed several JSON objects: a one-line metadata header and a
    # multi-line body. Try every column-0 '{' as a JSON start.
    starts = [0] + [m.start() for m in re.finditer(r"(?m)^\{", text)]
    for pos in starts:
        try:
            obj, _ = dec.raw_decode(text, pos)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if meta is None and "bug_type" in obj:
            meta = obj
        if body is None and isinstance(obj.get("threads"), list):
            body = obj
            if meta is not None:
                break
    if body is None:
        raise ParseError('no JSON object with a "threads" list (not a crash/hang .ips)')
    return meta or {}, body


def _norm_subtype(s: str) -> str:
    """KERN_INVALID_ADDRESS at 0x1d7b... -> KERN_INVALID_ADDRESS at 0xADDR."""
    return re.sub(r"0x[0-9a-fA-F]+", "0xADDR", s)


def _addr_class(far) -> str:
    if far is None:
        return "unknown"
    return "near-null" if far < NEAR_NULL_LIMIT else "wild"


def _app_image_index(images, bundle):
    for i, img in enumerate(images):
        if bundle and img.get("CFBundleIdentifier") == bundle:
            return i
    for i, img in enumerate(images):
        if str(img.get("path", "")).startswith("/Applications/") and img.get("uuid"):
            return i
    return None


def sig_from(body, meta, source=""):
    """Extract the deterministic signature dict from a .ips JSON body."""
    bi = body.get("bundleInfo") or {}
    bundle = bi.get("CFBundleIdentifier") or ""
    images = body.get("usedImages") or []
    threads = body.get("threads") or []

    idx = body.get("faultingThread")
    if not isinstance(idx, int) or not (0 <= idx < len(threads)):
        idx = next((i for i, th in enumerate(threads) if th.get("triggered")), 0)
    try:
        th = threads[idx]
    except IndexError:
        raise ParseError("faultingThread out of range") from None

    state = th.get("threadState") or {}
    far = (state.get("far") or {}).get("value")
    exc = body.get("exception") or {}
    kind_vals = (
        exc.get("type") or "",
        exc.get("signal") or "",
        _norm_subtype(exc.get("subtype") or ""),
        _addr_class(far),
    )
    app_idx = _app_image_index(images, bundle)
    app_uuid = (images[app_idx].get("uuid") or "") if app_idx is not None else ""
    offsets = [
        f["imageOffset"]
        for f in (th.get("frames") or [])
        if f.get("imageIndex") == app_idx and isinstance(f.get("imageOffset"), int)
    ]
    sig = {
        "source": str(source),
        "bundle": bundle,
        "version": bi.get("CFBundleShortVersionString") or "",
        "build": bi.get("CFBundleVersion") or "",
        "app_uuid": app_uuid,
        "exc_type": kind_vals[0],
        "exc_signal": kind_vals[1],
        "exc_subtype_norm": kind_vals[2],
        "addr_class": kind_vals[3],
        "queue": th.get("queue") or "",
        "offsets": offsets,
        "incident": meta.get("incident_id") or "",
        "bug_type": meta.get("bug_type") or "",
    }
    core = {k: sig[k] for k in ("bundle", "app_uuid", "exc_type", "exc_signal",
                                "exc_subtype_norm", "addr_class", "queue")}
    core["offsets3"] = offsets[:PREFIX_FRAMES]
    sig["fp"] = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return sig


def kind(sig):
    return (sig["exc_type"], sig["exc_signal"],
            sig["exc_subtype_norm"], sig["addr_class"])


def _prefix_match(a, b):
    n = min(PREFIX_FRAMES, len(a), len(b))
    if n == 0:
        return False          # nothing comparable -> refuse T1
    return a[:n] == b[:n]


def _qs(a, b):
    q = a["queue"] or b["queue"]
    return f" ({q})" if q else ""


def compare(a, b):
    """Apply the pairwise rule table. Returns (tier, reason)."""
    if a["bundle"] != b["bundle"]:
        return T_SKIP, "different app bundle"
    if kind(a) != kind(b):
        return T_SKIP, "same app, different exception kind"
    same_uuid = bool(a["app_uuid"]) and a["app_uuid"] == b["app_uuid"]
    same_queue = (not a["queue"] or not b["queue"]) or a["queue"] == b["queue"]
    if same_uuid:
        if _prefix_match(a["offsets"], b["offsets"]) and same_queue:
            return T1, "same build + matching top app-frame offsets" + _qs(a, b)
        if same_queue:
            return T2, "same build + kind, app-frame offsets differ" + _qs(a, b)
        return T_INFO, "same build + kind, different queue"
    if same_queue:
        return T2, "different build + same kind + same queue" \
                   " (offsets may shift across builds)" + _qs(a, b)
    return T_INFO, "same app + kind, different build/queue"


def load_repo_sigs(repo_root: Path, verbose=False):
    """[(issue_dir, [sig, ...]), ...] + count of unparsable files."""
    issues = []
    unparsable = 0
    for plat in PLATFORM_DIRS:
        base = repo_root / plat
        if not base.is_dir():
            continue
        for idir in sorted(p for p in base.iterdir() if p.is_dir()):
            sigs = []
            ev = idir / "evidence"
            if ev.is_dir():
                for f in sorted(ev.glob("*.ips")):
                    try:
                        meta, body = parse_ips(f.read_text(errors="replace"))
                        sigs.append(sig_from(body, meta, source=f))
                    except ParseError:
                        unparsable += 1
                        print(f"WARNING: unparsable .ips skipped: {f}", file=sys.stderr)
            if verbose:
                print(f"  {idir}: {len(sigs)} signature(s)")
            issues.append((idir, sigs))
    return issues, unparsable


def new_sig(path) -> dict:
    meta, body = parse_ips(Path(path).read_text(errors="replace"))
    return sig_from(body, meta, source=path)


def _one_line(sig):
    return (f"{sig['bundle']} {sig['version']} ({sig['build']}) "
            f"queue={sig['queue']!r} offsets={sig['offsets'][:PREFIX_FRAMES]}")


def finish(matches):
    if any(m[0] == T1 for m in matches):
        return 10
    if any(m[0] == T2 for m in matches):
        return 11
    return 0


def check_new(repo_root: Path, path, verbose=False) -> int:
    try:
        sig = new_sig(path)
    except (ParseError, OSError) as e:
        print(f"ERROR: cannot parse {path}: {e}", file=sys.stderr)
        return 3
    issues, _bad = load_repo_sigs(repo_root, verbose)
    n = sum(len(s) for _, s in issues)
    print(f"== new report: {path}")
    if verbose:
        print(json.dumps(sig, indent=2))
    print(f"   fp {sig['fp']}  {_one_line(sig)}")
    print(f"== against  : {len(issues)} issue dir(s) / {n} signature(s)")
    matches = []
    for idir, sigs in issues:
        for s in sigs:
            tier, reason = compare(sig, s)
            if tier > T_SKIP:
                matches.append((tier, reason, str(idir), s))
    code = finish(matches)
    for t, reason, idir, s in sorted(matches, key=lambda m: -m[0]):
        print(f"\n{LABEL[t]} -> {idir}")
        print(f"  reason : {reason}")
        print(f"  match  : {s['source']}")
        print(f"  fp     : {s['fp']}   {_one_line(s)}")
        if t in (T1, T2):
            print(ACTION_RECURRENCE if t == T1 else ACTION_POSSIBLE)
    print(f"\nRESULT: {'RECURRENCE' if code == 10 else 'POSSIBLE' if code == 11 else 'CLEAN'}"
          f" — exit {code}")
    return code


def scan_all(repo_root: Path, verbose=False) -> int:
    issues, bad = load_repo_sigs(repo_root, verbose)
    n = sum(len(s) for _, s in issues)
    tail = f", {bad} unparsable skipped" if bad else ""
    print(f"== scan-all: {len(issues)} issue dir(s), {n} signature(s){tail} ==")
    matches = []
    for (da, sa), (db, sb) in itertools.combinations(issues, 2):
        for x in sa:
            for y in sb:
                tier, reason = compare(x, y)
                if tier > T_SKIP:
                    matches.append((tier, reason, f"{da.name} <-> {db.name}", y))
    code = finish(matches)
    for t, reason, pair, s in sorted(matches, key=lambda m: -m[0]):
        print(f"\n{LABEL[t]} {pair}")
        print(f"  reason : {reason}")
        print(f"  sig B  : {s['source']}  fp={s['fp']}")
    print(f"\nRESULT: {'RECURRENCE' if code == 10 else 'POSSIBLE' if code == 11 else 'CLEAN'}"
          f" — exit {code}")
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="deterministic duplicate/recurrence check for .ips evidence")
    ap.add_argument("ips", nargs="?", help="new .ips report to check")
    ap.add_argument("--scan-all", action="store_true",
                    help="pairwise cross-check of every committed evidence/*.ips")
    ap.add_argument("--verbose", action="store_true",
                    help="print extracted signatures")
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent,
                    help="repo root (default: directory containing this script)")
    args = ap.parse_args(argv)
    if args.scan_all and args.ips:
        ap.error("choose either <ips> or --scan-all, not both")
    if args.scan_all:
        return scan_all(args.repo, args.verbose)
    if not args.ips:
        ap.print_usage()
        return 2
    return check_new(args.repo, args.ips, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
