---
date: 2026-11-11
status: open
severity: minor
platform: macOS
component: pdfdump (first-party CLI, skim build/tools)
---

# pdfdump NSInvalidArgumentException in `main`: `objectForKey:` sent to a bridgeless CoreGraphics type

## Summary

`pdfdump`, a first-party CLI (CGPDF page-geometry / PDFKit dumper built from
`skim/build/tools/pdfdump.m`), crashed at 2026-11-11 13:44:41 +0700, ~0.7 s
after launch (13:44:40.43), with an uncaught `NSInvalidArgumentException`:
`-[__NSCFType objectForKey:]: unrecognized selector sent to instance
0x1036e5030`. `main` sent an NSDictionary-style selector to a plain
CoreFoundation/CoreGraphics object — the ObjC runtime reports such non-ObjC
types as `__NSCFType` — and the forwarding machinery raised and terminated
the process (SIGABRT). This is a **first-party** (`is_first_party: 1`,
`codeSigningID: pdfdump`, empty signing team, `developerMode: 1`) report:
the binary was replaced by a rebuild **10 s after the crash**, so the code
that crashed no longer exists on disk.

## Environment

- macOS: 27.2.1 (build 26B131), SIP enabled
- Hardware: Model Identifier `Mac15,3`, Apple M3, 8 GB LPDDR5
- Affected software:
  - Name: `pdfdump` (CLI; no bundle identifier, version n/a, `Identifier: ???`)
  - Build UUID (crashed build): `8be59005-9f2d-3bce-98ed-f3525abe1081`
  - Install source: local developer build (`skim/build/tools/pdfdump.m`,
    clang, ad-hoc signed)
- Reproducibility: once (single launch during a dev iteration; source mtime
  13:44:46 and rebuilt binary 13:44:51 — both **after** the 13:44:41 crash)
- State at observation: boot session `1B27F0B7-…` (same boot as the recorded
  Wacom Center and Sourcetree incidents); uptime 13000 s; launched from
  iTerm2, parent shell already exited at capture

## Observed debug messages

Source: macOS crash reporter `.ips` (bug_type 309). Verbatim excerpt of the
exception and the app-side frames:

```
Exception Type:    EXC_CRASH (SIGABRT)
Exception Reason:  -[__NSCFType objectForKey:]: unrecognized selector sent to instance 0x1036e5030

Last Exception Backtrace:
2   CoreFoundation                 ...  -[NSObject(NSObject) __retain_OA] + 0
3   CoreFoundation                 ...  ___forwarding___ + 1504
4   CoreFoundation                 ...  _CF_forwarding_prep_0 + 96
5   pdfdump                        0x102fc8af8  main + 648
6   dyld                           ...  start + 6652

Thread 0 Crashed::  Dispatch queue: com.apple.main-thread
10  CoreFoundation                 ...  -[NSObject(NSObject) doesNotRecognizeSelector:] + 384
11  CoreFoundation                 ...  ___forwarding___ + 1504
12  CoreFoundation                 ...  _CF_forwarding_prep_0 + 96
13  pdfdump                        0x102fc8af8  main + 648
```

The app-side backtrace has exactly **one frame** (`main + 648`): the
`objectForKey:` send was made directly by `main`, with no framework frame
in between. System frames (`abort`, `objc_exception_throw`,
`doesNotRecognizeSelector:`, `___forwarding___`) are the standard
uncaught-ObjC-exception chain, not a memory fault.

Evidence files:

- `evidence/pdfdump-2026-11-11-134443.ips` — full report (two-part JSON +
  trailing system profile); one device serial redacted (see Privacy screen).

## Collection commands used

```sh
cp ~/Library/Logs/DiagnosticReports/pdfdump-2026-11-11-134443.ips \
   macos/2026-11-11-pdfdump-objectforkey-unrecognized-selector/evidence/
# redact Kindle Scribe en7 NIC serial from the trailing system profile
# (literal token elided from these docs by policy; evidence copy shows
#  the result as <REDACTED-SERIAL>)
sed -i '' 's/<Kindle-serial>/<REDACTED-SERIAL>/g' \
   evidence/pdfdump-2026-11-11-134443.ips
./check_duplicates.py ~/Library/Logs/DiagnosticReports/pdfdump-2026-11-11-134443.ips
# → RESULT: CLEAN, exit 0  (new issue)
```

## Steps to reproduce

1. Not available against the crashed build: the binary under
   `skim/build/tools/` was overwritten 10 s after the capture (current
   build UUID `7C3B091A-3172-3735-9F95-5BC5363263A7`), and the dev-loop
   source at crash time is not in git (untracked build directory).
2. The surviving tool takes one PDF path argument; the invocation at
   13:44:40 (argv) was not captured.

## Expected vs actual

- Expected: page-geometry dump via typed CoreGraphics accessors, or a
  graceful failure message on unusable input.
- Actual: uncaught `NSInvalidArgumentException` raised in `main`;
  process aborted (SIGABRT).

## Analysis

Observed facts:

- The receiver's class as printed by the exception is `__NSCFType` — how
  the ObjC runtime presents a plain (non-toll-free-bridged) CoreFoundation
  / CoreGraphics object, e.g. `CGPDFDictionaryRef`.
- The send of `objectForKey:` originated in `main` itself: a single app
  frame directly beneath `_CF_forwarding_prep_0`.
- The current build contains **no** `objectForKey:` selector string
  (`strings -a pdfdump | grep -i objectfor` → 0 matches), and the
  surviving source (`pdfdump.m`) reads page dictionaries only through
  typed `CGPDFDictionaryGetNumber` / `GetDictionary` / `GetArray`. The
  crashed build therefore ran materially different code.
- Symbolication of `main + 648` against the crashed build
  (`8be59005-…`) is impossible; that binary was overwritten.

Interpretation (hypothesis — labeled, not proven):

- The crashed iteration most plausibly passed a `CGPDFDictionaryRef` (or a
  similar CF-typed container) to `objectForKey:` / dictionary subscripting
  instead of the typed accessors. Such types are not toll-free-bridged to
  `NSDictionary`, which produces exactly this forwarding failure; the
  13:44:46 edit (5 s post-crash) and the 13:44:51 rebuild look like the
  in-flight fix, and the surviving source is consistent with it. A
  fallback reading — a different bridgeless CF receiver — is not excluded,
  but it changes neither the fix nor the analysis above.
- Checker caveat, documented for future recurrences: this is a first-party
  report, and `check_duplicates.py` only counts `/Applications/…`+UUID
  images as "the app"; bundle, app UUID and top-frame offsets degrade to
  empty and the fingerprint collapses to exception kind + dispatch queue
  (`e3fdfedbc3bc3369` — shared with the same-minute `cropzoom` incident on
  this issue index). For first-party reports, disambiguate recurrences
  manually by slice/build UUID and incident ID.

## Impact and workaround

- Impact: development-only; a scratch tool in an active iteration aborted
  once. No data loss (read-only dumper); no systemic effect.
- Workaround: in-place — the tool was rebuilt at 13:44:51 with the send
  removed; the surviving source cannot produce this exception. Record one
  clean post-fix run of the tool to move this entry to `resolved`.

## Upstream report

- Where: N/A — first-party tool; the fix lives in the local source
  (`skim/build/tools/pdfdump.m`), not a vendor tracker.
- Status: not applicable

## Privacy screen (per README policy)

- **Redacted one device serial**: the trailing system profile identifies
  `Network Service: Kindle Scribe <REDACTED-SERIAL>` (`en7`); the serial
  token was replaced in the evidence copy and is not reproduced in these
  docs.
- Scanned for email / username / home-paths / SSID / tokens: none present
  (`procPath` arrives pre-redacted by Apple as `/Users/USER/*/pdfdump`).
- Kept deliberately (pseudonymous): incident id `661A4BBA-…`, slice/build
  UUID `8be59005-…`, crash reporter key, boot/sleep-wake UUIDs.
- `User ID: 503` is a local POSIX uid.

## Recurrences

One row per later occurrence confirmed by `./check_duplicates.py <new .ips>`
(exit 10; README → "Duplicate / recurrence check"). Same fingerprint means
the same issue — append a row here and commit another `.ips` under
`evidence/`; **never** scaffold a new issue for it. Note the first-party
fingerprint caveat above: verify the build UUID manually before recording.

| Date | Fingerprint | Incident ID | Evidence file | Note |
|------|-------------|-------------|---------------|------|
| 2026-11-11 (first) | `e3fdfedbc3bc3369` | `661A4BBA-624D-4E28-ADA3-43BC7ED82885` | `pdfdump-2026-11-11-134443.ips` | founding crash; build `8be59005-…`, receiver `__NSCFType` |
