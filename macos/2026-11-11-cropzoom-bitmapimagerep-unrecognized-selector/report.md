---
date: 2026-11-11
status: open
severity: minor
platform: macOS
component: cropzoom (first-party CLI, skim build/tools)
---

# cropzoom NSInvalidArgumentException in `main`: `initWithContentsOfFile:` sent to `NSBitmapImageRep`

## Summary

`cropzoom`, a first-party CLI (PNG region-crop + nearest-neighbor zoom,
built from `skim/build/tools/cropzoom.m`), crashed at 2026-11-11 13:45:46
+0700, ~0.4 s after launch (13:45:46.29), with an uncaught
`NSInvalidArgumentException`: `-[NSBitmapImageRep initWithContentsOfFile:]:
unrecognized selector sent to instance 0x1054a9040`. The receiver was a
valid `NSBitmapImageRep` — the defect is the selector: the call used an
instance initializer that does not exist anywhere on the `NSImageRep`
class family, so the ObjC forwarding machinery raised and the process
aborted (SIGABRT). This is a **first-party** (`is_first_party: 1`,
`codeSigningID: cropzoom`, empty signing team, `developerMode: 1`)
report: the binary was rebuilt right after the crash. One minute earlier
the sibling first-party tool `pdfdump` crashed with the same exception
family during the same dev iteration — different process, different code
path (see sibling issue on this index); unrelated to it.

## Environment

- macOS: 27.2.1 (build 26B131), SIP enabled
- Hardware: Model Identifier `Mac15,3`, Apple M3, 8 GB LPDDR5
- Affected software:
  - Name: `cropzoom` (CLI; no bundle identifier, version n/a, `Identifier: ???`)
  - Build UUID (crashed build): `1d4d6cb1-d0e9-3531-a521-b90887ec6b33`
  - Install source: local developer build (`skim/build/tools/cropzoom.m`,
    clang, ad-hoc signed)
- Reproducibility: deterministic by construction at crash-time code
  (below); single incident recorded
- State at observation: boot session `1B27F0B7-…` (same boot as the
  recorded Wacom Center, Sourcetree and pdfdump incidents); uptime
  13000 s; launched from iTerm2, parent shell already exited at capture

## Observed debug messages

Source: macOS crash reporter `.ips` (bug_type 309). Verbatim excerpt of the
exception and the app-side frames:

```
Exception Type:    EXC_CRASH (SIGABRT)
Exception Reason:  -[NSBitmapImageRep initWithContentsOfFile:]: unrecognized selector sent to instance 0x1054a9040

Last Exception Backtrace:
2   CoreFoundation                 ...  -[NSObject(NSObject) __retain_OA] + 0
3   CoreFoundation                 ...  ___forwarding___ + 1504
4   CoreFoundation                 ...  _CF_forwarding_prep_0 + 96
5   cropzoom                       0x104cac904  main + 260
6   dyld                           ...  start + 6652

Thread 0 Crashed::  Dispatch queue: com.apple.main-thread
10  CoreFoundation                 ...  -[NSObject(NSObject) doesNotRecognizeSelector:] + 384
11  CoreFoundation                 ...  ___forwarding___ + 1504
12  CoreFoundation                 ...  _CF_forwarding_prep_0 + 96
13  cropzoom                       0x104cac904  main + 260
```

The app-side backtrace has exactly **one frame** (`main + 260`): the send
was made directly by `main`, early in the program (PNG input loading).

SDK fact (hard evidence): the macOS SDK header
`AppKit.framework/Headers/NSImageRep.h` declares, for file-backed image
representation creation, only the **class** factory

```objc
+ (nullable NSImageRep *)imageRepWithContentsOfFile:(NSString *)filename;
```

and the instance method `-initWithData:` — there is **no instance-level
`-initWithContentsOfFile:`** on `NSImageRep` or `NSBitmapImageRep`.
`[[NSBitmapImageRep alloc] initWithContentsOfFile:…]` therefore ends in
`-doesNotRecognizeSelector:` on every run.

Evidence files:

- `evidence/cropzoom-2026-11-11-134547.ips` — full report (two-part JSON +
  trailing system profile); one device serial redacted (see Privacy screen).

## Collection commands used

```sh
cp ~/Library/Logs/DiagnosticReports/cropzoom-2026-11-11-134547.ips \
   macos/2026-11-11-cropzoom-bitmapimagerep-unrecognized-selector/evidence/
# redact Kindle Scribe en7 NIC serial from the trailing system profile
# (literal token elided from these docs by policy; evidence copy shows
#  the result as <REDACTED-SERIAL>)
sed -i '' 's/<Kindle-serial>/<REDACTED-SERIAL>/g' \
   evidence/cropzoom-2026-11-11-134547.ips
./check_duplicates.py ~/Library/Logs/DiagnosticReports/cropzoom-2026-11-11-134547.ips
# → RESULT: CLEAN, exit 0  (new issue)
```

## Steps to reproduce

1. Deterministic (developer error, not input-dependent): call
   `[[NSBitmapImageRep alloc] initWithContentsOfFile:<some .png path>]` in
   any client of AppKit and run it — the same
   `unrecognized selector` exception is raised on every run.
2. The crashed build `1d4d6cb1-…` itself is gone: `cropzoom` in
   `skim/build/tools/` was rebuilt minutes after the capture (current
   build UUID `5834FFF8-C8EE-38F2-B624-AB9B0A7C4186`), and `cropzoom.m`
   (mtime 13:45) no longer contains the call.

## Expected vs actual

- Expected: input PNG loaded into an `NSBitmapImageRep` (via
  `+imageRepWithContentsOfFile:`, `initWithData:`, or a CGImageSource
  round-trip) so the crop/zoom loop can read pixels.
- Actual: uncaught `NSInvalidArgumentException` raised in `main`;
  process aborted (SIGABRT).

## Analysis

Observed facts:

- Selector `initWithContentsOfFile:` was sent to a live
  `NSBitmapImageRep` instance and only AppKit's
  `-doesNotRecognizeSelector:` machinery responded — no AppKit frame
  attempted to honor the send.
- The send originated in `main` itself (single app frame, offset +260).
- The current build contains **no** `initWithContentsOfFile:` selector
  string (`strings -a cropzoom | grep -iF 'initWithContentsOfFile'` →
  0 matches); the surviving source loads the input through
  `CGImageSourceCreateWithURL` + `CGImageSourceCreateImageAtIndex` and
  draws into a pre-sized rep created with
  `initWithBitmapDataPlanes:…`.
- PNG files written by the rebuilt tool (`crop_p0_direct.png`,
  `crop_p0_pdfkit.png`, 13:48, build dir) are consistent with a successful
  post-fix run (the attribution of those outputs to `cropzoom` is inferred
  from the naming pattern of the same tool).

Interpretation (labeled):

- The crashed iteration fetched its input file with the nonexistent
  instance initializer instead of the class factory
  `+imageRepWithContentsOfFile:` (or an equivalent). The 13:45 rebuild is
  the in-flight fix; the surviving source's CGImageSource pipeline cannot
  produce this exception.
- Checker caveat, documented for future recurrences: this is a first-party
  report, and `check_duplicates.py` only counts `/Applications/…`+UUID
  images as "the app"; bundle, app UUID and top-frame offsets degrade to
  empty and the fingerprint collapses to exception kind + dispatch queue
  (`e3fdfedbc3bc3369` — shared with the same-minute `pdfdump` incident).
  For first-party reports, disambiguate recurrences manually by
  slice/build UUID and incident ID.

## Impact and workaround

- Impact: development-only; a scratch tool in an active iteration aborted
  during one run. No data loss (input PNG untouched).
- Workaround: in-place — the rebuilt tool (current source) works; the
  general fix for the pattern is `+imageRepWithContentsOfFile:` or
  `[[NSBitmapImageRep alloc] initWithData:[NSData dataWithContentsOfFile:…]]`.

## Upstream report

- Where: N/A — first-party tool; the fix lives in the local source
  (`skim/build/tools/cropzoom.m`), not a vendor tracker.
- Status: not applicable

## Privacy screen (per README policy)

- **Redacted one device serial**: the trailing system profile identifies
  `Network Service: Kindle Scribe <REDACTED-SERIAL>` (`en7`); the serial
  token was replaced in the evidence copy and is not reproduced in these
  docs.
- Scanned for email / username / home-paths / SSID / tokens: none present
  (`procPath` arrives pre-redacted by Apple as `/Users/USER/*/cropzoom`).
- Kept deliberately (pseudonymous): incident id `93224DCF-…`, slice/build
  UUID `1d4d6cb1-…`, crash reporter key, boot/sleep-wake UUIDs.
- `User ID: 503` is a local POSIX uid.

## Recurrences

One row per later occurrence confirmed by `./check_duplicates.py <new .ips>`
(exit 10; README → "Duplicate / recurrence check"). Same fingerprint means
the same issue — append a row here and commit another `.ips` under
`evidence/`; **never** scaffold a new issue for it. Note the first-party
fingerprint caveat above: verify the build UUID manually before recording.

| Date | Fingerprint | Incident ID | Evidence file | Note |
|------|-------------|-------------|---------------|------|
| 2026-11-11 (first) | `e3fdfedbc3bc3369` | `93224DCF-4A05-4240-A24F-F8F7BED619BF` | `cropzoom-2026-11-11-134547.ips` | founding crash; build `1d4d6cb1-…`, nonexistent instance initializer |
