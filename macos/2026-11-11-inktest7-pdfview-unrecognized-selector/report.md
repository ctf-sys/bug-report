---
date: 2026-11-11
status: open
severity: minor
platform: macOS
component: inktest7 (first-party CLI, skim build/tools)
---

# inktest7 NSInvalidArgumentException: a selector literally named `%s` sent to `PDFView` in `main` (2 incidents, same build)

## Summary

`inktest7`, a first-party CLI in the same Skim dev iteration as the recorded
`pdfdump` and `cropzoom` issues (see index), crashed **twice within 3
seconds** (2026-11-11 13:52:34, pid 31724 and 13:52:37, pid 31738), each
~0.6 s after launch, with an uncaught `NSInvalidArgumentException` whose
message is unlike the two sibling crashes:

```
-[PDFView %s]: unrecognized selector sent to instance 0x770f2bc280
```

The selector **name itself** is the two-character literal string `%s` —
not a misspelled real selector. The receiver is a genuine `PDFView` (0x770f
2bc280). Both incidents failed at the identical offset (`main + 1616`) on
identical builds, a few tenths of a second into a live offscreen PDF render
pipeline (PDFKit tile-pool thread was mid-render). The crashed build's
source was replaced ~20 s after the second crash (`inktest7.m` 13:52:53,
binary 13:52:57, UUID `4AC91DA1-…`); the dev loop then moved on to
`inktest8.m` (13:53).

## Environment

- macOS: 27.2.1 (build 26B131), SIP enabled
- Hardware: Model Identifier `Mac15,3`, Apple M3, 8 GB LPDDR5
- Affected software:
  - Name: `inktest7` (CLI; no bundle identifier, version n/a)
  - Build UUID (crashed build): `3ab90adf-fdd1-3b5b-8197-0a58084a4abe`
    (both incidents)
  - PDFKit `1537.1.4`, AppKit `2775.20.133`, QuartzCore `1223.10.17.2`,
    Metal `383.1` (system, 26B131)
  - Install source: local developer build (`skim/build/tools/inktest7.m`,
    clang, ad-hoc signed)
- Reproducibility: 2/2 runs of the crashed build (13:52:33.76 and
  13:52:37.02 launches)
- State at observation: boot session `1B27F0B7-…` (same boot as the
  Wacom / Sourcetree / pdfdump / cropzoom incidents); uptime 14000 s;
  launched from iTerm2 (parent shell exited at capture)

## Observed debug messages

Source: macOS crash reporter `.ips` (bug_type 309, both files). Verbatim
excerpt of the exception and app-side frames:

```
Exception Type:    EXC_CRASH (SIGABRT)
Exception Reason:  -[PDFView %s]: unrecognized selector sent to instance 0x770f2bc280

Last Exception Backtrace:
2   CoreFoundation                 ...  -[NSObject(NSObject) __retain_OA] + 0
3   CoreFoundation                 ...  ___forwarding___ + 1504
4   CoreFoundation                 ...  _CF_forwarding_prep_0 + 96
5   inktest7                       0x104c84fc8  main + 1616
6   dyld                           ...  start + 6652

Thread 0 Crashed::  Dispatch queue: com.apple.main-thread
10  CoreFoundation                 ...  -[NSObject(NSObject) doesNotRecognizeSelector:] + 384
11  CoreFoundation                 ...  ___forwarding___ + 1504
12  CoreFoundation                 ...  _CF_forwarding_prep_0 + 96
13  inktest7                       0x104c84fc8  main + 1616
```

Supporting context (second thread) — the process was a *live* offscreen
renderer when main-thread crashed; render pipeline was mid-flight, not idle:

```
Thread 1::  Dispatch queue: PDFKit.PDFTilePool.workQueue
3   libdispatch   __DISPATCH_WAIT_FOR_QUEUE__ + 432
4   libdispatch   _dispatch_sync_f_slow + 144
5   QuartzCore    CA::CG::ContextDelegate::operation_(...) + 196
6   PDFKit        -[PDFPage drawWithBox:toContext:] + 136
7   PDFKit        -[PDFView drawPage:] + 68
9   PDFKit        __37-[PDFTilePool _renderTileForRequest:]_block_invoke + 144
```

Thread 2 (`CA::CG::Queue`) was compiling a Metal shader from a binary
archive at the same moment; Thread 8 is the crash reporter's own
thread-suspension pass (`HIServices` `SOME_OTHER_THREAD_SWALLOWED_AT_LEAST
_ONE_EXCEPTION` above `thread_suspend`) — part of uncaught-exception
reporting, not an independent fault.

Evidence files:

- `evidence/inktest7-2026-11-11-135236.ips` — incident `B7C8CBB2-…`
  (pid 31724, founding crash)
- `evidence/inktest7-2026-11-11-135237.ips` — incident `C2D0F4F2-…`
  (pid 31738, immediate repeat, identical build + offsets)

## Collection commands used

```sh
cp ~/Library/Logs/DiagnosticReports/inktest7-2026-11-11-135236.ips \
   ~/Library/Logs/DiagnosticReports/inktest7-2026-11-11-135237.ips \
   macos/2026-11-11-inktest7-pdfview-unrecognized-selector/evidence/
./check_duplicates.py ~/Library/Logs/DiagnosticReports/inktest7-2026-11-11-135237.ips
# → RESULT: POSSIBLE, exit 11 (first-party fingerprint) — see Analysis
```

## Steps to reproduce

1. Reproduced against the crashed build twice by the dev loop itself
   (13:52:33.76 and 13:52:37.02 launches, identical failure); the build
   was replaced at 13:52:57 before any controlled rerun could be made.
2. No repro on the surviving build is attempted: `inktest7.m` was
   rewritten 13:52:53 / rebuilt 13:52:57 (UUID `4AC91DA1-…`) and the
   iteration moved to `inktest8.m`; the crashed source is not on disk or
   in git (untracked build directory).

## Expected vs actual

- Expected: offscreen PDFView render of a red ink annotation; raster
  analysis output (AA ratio / ASCII grid); PNG written.
- Actual: uncaught `NSInvalidArgumentException` in `main` ~0.6 s into the
  run; process aborted before any output (no `*_view.png` written by the
  crashing runs).

## Analysis

Checker verdict and manual review (exit 11 handling, per README):
`check_duplicates.py` answered **POSSIBLE** against the pdfdump issue —
`different build + same kind + same queue`. This is the degenerate
first-party fingerprint documented in the sibling reports: for
`/Users/…`-resident ad-hoc binaries the extractor keeps no bundle, app
UUID or top-frame offsets, so the fingerprint collapses to exception kind
+ queue (`e3fdfedbc3bc3369`, shared by pdfdump/cropzoom/inktest7). Manual
review decides:

- pdfdump 13:44:41 — `objectForKey:` sent to `__NSCFType`: different.
- cropzoom 13:45:46 — `initWithContentsOfFile:` sent to `NSBitmapImageRep`:
  different.
- inktest7 — literal `%s` selector sent to `PDFView`: **new issue**
  (this one). The two inktest7 incidents are same-build, same-offset,
  same-selector → recorded here as recurrence rows, not as a duplicate
  issue.

Observed facts:

- A selector **registered under the name `%s`** was sent to a `PDFView`
  instance. The ObjC runtime prints selector names verbatim (both sibling
  reports show real names), so `%s` is genuinely the registered name, not
  an output-formatting artifact of the report.
- The send originated directly in `main` (single app frame, offset +1616),
  ~0.6 s after launch — after tool argument parsing, on the render path.
- Selectors are interned strings; the name `%s` can only exist if some
  code registered it (`sel_registerName` / `NSSelectorFromString` / a
  `char *` cast to `SEL` used as a selector).
- The post-crash `inktest7.m` (13:52:53) contains **no** dynamic selector
  construction at all — every PDFView/AppKit message is a compile-time
  selector — and no `%s`-containing format passed to any receiver; the
  crashed iteration's source therefore contained the defect and was
  removed in the 13:52:53 edit (`4AC91DA1-…` build at 13:52:57).
- During both crashes the app-side work was windowless offscreen
  rendering (`displayRectIgnoringOpacity:inContext:`) with PDFKit's tile
  pool and a Metal shader compile running on background queues; the tiles
  were already rendering when main tripped — background threads are
  context, not the faulting code.

Interpretation (hypotheses — labeled, not proven):

- **Primary hypothesis:** the crashed iteration built a selector
  dynamically — e.g. `performSelector:`/`objc_msgSend` with a selector
  obtained from `NSSelectorFromString` on a printf-built string, or a
  `char *` cast to `SEL` — and the string ended up as the literal `%s`,
  most plausibly a format/argument mismatch inside that selector-name
  construction (the very pattern `%s` names). First send lazily interned
  `%s` as a selector; `PDFView` did not implement it; forwarding raised.
- **Fallback kept open:** any other mechanism interning a two-char
  garbage selector (e.g. casting a non-NUL-terminated or short C buffer
  to `SEL`). Both hypotheses agree on the fix direction evident in the
  surviving source: keep every message send compile-time.
- The surviving-inktest7 path itself (`inktest8` inherits it) is the
  post-fix behavior; no further `inktest7` .ips appeared after 13:52:37
  (checked at 13:53:0x), consistent with the fix being effective.

## Impact and workaround

- Impact: development-only; the tool aborted before producing any output
  on both runs of the crashed build. No data loss (read-only inputs).
- Workaround: in-place — source rewritten and rebuilt 20 s after the last
  crash; no dynamic selector sends remain in the surviving tool. Record a
  clean post-fix run to move this entry to `resolved`.

## Upstream report

- Where: N/A — first-party tool; fix lives in the local source
  (`skim/build/tools/inktest7.m` → `inktest8.m`), not a vendor tracker.
- Status: not applicable

## Privacy screen (per README policy)

- Scanned both evidence files for email / device serial / username-paths /
  SSID / tokens: none present; the two `.ips` files carry no trailing
  system profile at all, and `procPath` arrives pre-redacted
  by Apple as `/Users/USER/*/inktest7`.
- Kept deliberately (pseudonymous): incident ids `B7C8CBB2-…`,
  `C2D0F4F2-…`, slice/build UUID `3ab90adf-…`, crash reporter key,
  boot/sleep-wake UUIDs.
- `User ID: 503` is a local POSIX uid.

## Recurrences

One row per later occurrence confirmed by `./check_duplicates.py <new .ips>`
(exit 10; README → "Duplicate / recurrence check"). Same fingerprint means
the same issue — append a row here and commit another `.ips` under
`evidence/`; **never** scaffold a new issue for it. First-party caveat: the
checker cannot distinguish these issues (degenerate fingerprint, shared
with pdfdump/cropzoom) — verify the exception reason and build UUID
manually before recording.

| Date | Fingerprint | Incident ID | Evidence file | Note |
|------|-------------|-------------|---------------|------|
| 2026-11-11 (first) | `e3fdfedbc3bc3369` | `B7C8CBB2-9ECF-44F8-9A4F-4757BA82A61C` | `inktest7-2026-11-11-135236.ips` | founding crash; build `3ab90adf-…`, pid 31724, selector `%s` on `PDFView` |
| 2026-11-11 | `e3fdfedbc3bc3369` | `C2D0F4F2-8655-43C8-BAAC-1845BED43B27` | `inktest7-2026-11-11-135237.ips` | same build (`3ab90adf-…`), same offset `main+1616`, 3 s later; pid 31738 |
