---
date: 2026-11-11
status: open
severity: minor
platform: macOS
component: inktest8 (first-party CLI, skim build/tools)
---

# inktest8 NSInvalidArgumentException: a selector literally named `%s` sent to `NSBitmapImageRep` in `main` (2 incidents, same build)

## Summary

`inktest8`, the successor tool in the same Skim dev iteration as the
recorded `pdfdump` / `cropzoom` / `inktest7` crashes (see index), crashed
**twice within 48 s** (2026-11-11 13:53:50.52, pid 31915 and 13:54:38.18,
pid 32113), ~2.8 s and ~2.4 s after launch, with an uncaught
`NSInvalidArgumentException` bearing the same garbled-selector signature
as `inktest7` — but on a different receiver and offset:

```
-[NSBitmapImageRep %s]: unrecognized selector sent to instance 0x7b1498cd20   (incident 1)
-[NSBitmapImageRep %s]: unrecognized selector sent to instance 0x7a5655de30   (incident 2)
```

The selector **name itself** is the two-character literal string `%s`. The
receiver is a genuine `NSBitmapImageRep`. Both incidents failed at the
identical offset (`main + 2544`) on the identical build
(`508cf4a6-…`, binary written 13:53:47); the second crash re-ran **the same
binary with no rebuild** (dev edited the source at 13:54:31 before the
13:54:35 launch but only rebuilt at 13:54:44, producing a new build
`92179863-…` that overwrote the crashed binary). Unlike `inktest7`, this
run created a **real on-screen window** (PDFKit `visiblePagesChanged:`
fired), and the failing stage sits **after a successful compositor
capture** — the crashed code path only executes with a non-nil
`NSBitmapImageRep` loaded from the shot. A post-rebuild clean run at
14:00:57 (same input, same crash-region code, capture succeeding without a
debugger) did **not** crash; no `.ips` has appeared since 13:54:40.

## Environment

- macOS: 27.2.1 (build 26B131), SIP enabled, developer mode on
- Hardware: Model Identifier `Mac15,3`, Apple M3, 8 GB LPDDR5
- Affected software:
  - Name: `inktest8` (CLI; no bundle identifier, version n/a)
  - Build UUID (crashed build): `508cf4a6-ab7f-3e8c-a661-8605f0791cd9`
    (both incidents; verified on disk at 13:54:33 against the in-session
    dump before the 13:54:44 rebuild replaced it)
  - PDFKit `1537.1.4`, AppKit `2775.20.133`, Vision `10.1.7`,
    TextRecognition `157`, ANECompiler `10.205.4`, Espresso `3605.3.2`
    (system, 26B131)
  - Install source: local developer build (`skim/build/tools/inktest8.m`,
    clang, ad-hoc signed — `codeSigningID: inktest8`, no team id)
- Reproducibility: 2/2 runs of the crashed build (launches 13:53:47.74 and
  13:54:35.78); 0/1 on the rebuild (`92179863-…`, 14:00:57 run)
- State at observation: boot session `1B27F0B7-…` (same boot as the
  Wacom / Sourcetree / pdfdump / cropzoom / inktest7 incidents); launched
  from iTerm2 (responsible process iTerm2; parent process had already
  exited at capture — "Exited process"); uptime 14000 s.

## Observed debug messages

Source: macOS crash reporter `.ips` (bug_type 309, both files). Verbatim
excerpt of the exception and app-side frames (incident 1; incident 2 is
identical except pid/instance pointer/µs timestamps):

```
Exception Type:    EXC_CRASH (SIGABRT)
Exception Reason:  -[NSBitmapImageRep %s]: unrecognized selector sent to instance 0x7b1498cd20

Last Exception Backtrace:
2   CoreFoundation                 ...  -[NSObject(NSObject) __retain_OA] + 0
3   CoreFoundation                 ...  ___forwarding___ + 1504
4   CoreFoundation                 ...  _CF_forwarding_prep_0 + 96
5   inktest8                       0x102e093c8  main + 2544
6   dyld                           ...  start + 6652

Thread 0 Crashed::  Dispatch queue: com.apple.main-thread
10  CoreFoundation                 ...  -[NSObject(NSObject) doesNotRecognizeSelector:] + 384
11  CoreFoundation                 ...  ___forwarding___ + 1504
12  CoreFoundation                 ...  _CF_forwarding_prep_0 + 96
13  inktest8                       0x102e093c8  main + 2544
```

The crash reporter's structured exception reason carries the selector name
as a discrete argument — `"arguments": ["NSBitmapImageRep", "%s",
"0x7b1498cd20"]` — confirming `%s` is the *registered name*, not a
rendering artifact.

Supporting context (other threads) — the process was a live **windowed**
renderer when main tripped:

```
Thread 1::  Dispatch queue: com.apple.VN.detectorSyncTasksQueue.…
33  Vision        -[VNImageRequestHandler performRequests:gatheredForensics:error:] + 184
34  PDFKit        +[PDFPageAnalyzerV2 analyzePage:withBox:requestTypes:] + 900
35  PDFKit        __31-[PDFView visiblePagesChanged:]_block_invoke + 64
```

Thread 5 was compiling an ANE/Espresso E5 network AOT for the same Vision
request (Swift-concurrency completion frame at top). Thread 13 is the crash
reporter's own thread-suspension pass (`HIServices`
`SOME_OTHER_THREAD_SWALLOWED_AT_LEAST_ONE_EXCEPTION` above `thread_suspend`)
— part of uncaught-exception reporting, not an independent fault.
Background threads are context, not the faulting code.

Evidence files:

- `evidence/inktest8-2026-11-11-135354.ips` — incident `1E9FC492-…`
  (pid 31915, founding crash, launched 13:53:47.74)
- `evidence/inktest8-2026-11-11-135440.ips` — incident `5224214A-…`
  (pid 32113, immediate repeat on the same binary, launched 13:54:35.78;
  file carries 377 bytes of trailing non-JSON content after the body)

## Collection commands used

```sh
cp ~/Library/Logs/DiagnosticReports/inktest8-2026-11-11-135354.ips \
   ~/Library/Logs/DiagnosticReports/inktest8-2026-11-11-135440.ips \
   macos/2026-11-11-inktest8-bitmapimagerep-unrecognized-selector/evidence/
./check_duplicates.py --verbose ~/Library/Logs/DiagnosticReports/inktest8-2026-11-11-135354.ips
# → RESULT: POSSIBLE, exit 11 (first-party fingerprint) — see Analysis
./check_duplicates.py --verbose ~/Library/Logs/DiagnosticReports/inktest8-2026-11-11-135440.ips
# → RESULT: POSSIBLE, exit 11 (same degenerate fingerprint)
```

The crashed build was disassembled in-session between the two incidents
(binary still on disk, `dwarfdump --uuid` = `508CF4A6-…` verified
13:54:33); the crash-region listing was captured then and later
re-confirmed **byte-identical** on the surviving `92179863-…` build, so the
disassembly facts below hold for the crashed build.

## Steps to reproduce

1. The crashed build (`508cf4a6-…`, written 13:53:47) failed 2/2 runs
   (launches 13:53:47.74 and 13:54:35.78) with identical offset, receiver
   class and selector. The dev edited the source at 13:54:31 between the
   runs but did not rebuild until 13:54:44, so both incidents exercised the
   same binary.
2. Post-rebuild clean run 14:00:57 on the surviving build (`92179863-…`):
   `./inktest8 blank.pdf <prefix>` → exit 0, `screencapture` successful,
   full analysis output (bbox + ASCII grid) printed, no `.ips`. One run.
3. Debugger reproduction attempts, both blocked before the crash path:
   - 13:57:08 `lldb` launch of `inktest8` with a
     `doesNotRecognizeSelector:` breakpoint: `screencapture` exited 1
     under the launched debugger (window capture failed), the tool took
     its `capture failed` early-return (exit 1) and the breakpoint never
     fired. NOTE: by 13:57 the binary was already the rebuilt
     `92179863-…`, so this attempt also could not exercise the crashed
     build even had the capture succeeded.
   - Reproduction against the crashed build is no longer possible: the
     13:54:44 rebuild overwrote it, and no usable local Time Machine
     snapshot exists (only a dataless 2026-10-31 snapshot).

## Expected vs actual

- Expected: windowed PDFView render of a red ink annotation; compositor
  shot; PNG written; per-pixel analysis output (stroke bbox, AA ratio,
  ASCII grid).
- Actual: uncaught `NSInvalidArgumentException` ~2.5–2.8 s into the run,
  in the analysis stage that follows a successful capture (the crashing
  code path requires a non-nil `NSBitmapImageRep` built from the shot);
  the process aborted before its bbox/grid `NSLog` output.

## Analysis

Checker verdict and manual review (exit 11 handling, per README):
`check_duplicates.py` answered **POSSIBLE** on both files — `different
build + same kind + same queue` — against every existing issue. This is
the degenerate first-party fingerprint documented in the sibling reports:
for `/Users/…`-resident ad-hoc binaries the extractor keeps no bundle, app
UUID or top-frame offsets, so the fingerprint collapses to exception kind
+ queue (`e3fdfedbc3bc3369`, shared by pdfdump/cropzoom/inktest7).
Manual review decides:

- pdfdump — `objectForKey:` on `__NSCFType`, build `8be59005`: different.
- cropzoom — `initWithContentsOfFile:` on `NSBitmapImageRep`, build
  `1d4d6cb1`: different.
- inktest7 — `%s` on `PDFView`, build `3ab90adf`, `main+1616`: different
  receiver and offset, but **same defect family** (see hypotheses).
- inktest8 — `%s` on `NSBitmapImageRep`, build `508cf4a6`, `main+2544`:
  **new issue** (this one); its two incidents are same-build/same-offset →
  recorded here as a recurrence row.

Observed facts:

- A selector **registered under the name `%s`** was sent to a genuine
  `NSBitmapImageRep` on the main thread, ~2.5–2.8 s after launch, on the
  analysis stage that follows a compositor capture.
- Crashed frame = `main + 2544` (image offset 5064, vaddr
  `0x1000013c8`; `main` at `0x1000009d8`, runtime base `0x102e08000` in
  incident 1). The surrounding listing (identical in crashed and
  surviving builds):

  ```
  0x1000013a4  adrp x2, 3
  0x1000013a8  add  x2, x2, #0x1c0   ; CFString literal @ 0x1000041c0
  0x1000013ac  bl   _objc_msgSend$stringWithFormat:   ; [NSString stringWithFormat:@"%@ (scale %.2f)", prefix, sf]
  0x1000013b0  mov  x1, x0           ; label
  0x1000013b4  ldr  x0, [sp, #0x40]  ; rep
  0x1000013b8  bl   _analyzePNG      ; -> 0x16c8
  0x1000013bc  str  wzr, [sp, #0x29c]
  0x1000013c0  b    0x13c4
  0x1000013c4  ldr  x0, [sp, #0xf8]
  0x1000013c8  bl   autorelease pool pop stub
  ```

  The CFString at `0x1000041c0` is a healthy 15-byte literal — its utf8
  payload at file offset `0x263e` decodes exactly to `"%@ (scale %.2f)"`
  (length 0xf; otool's "bad cfstring ref" note is a chained-fixups
  decoding limitation, not corruption — the raw bytes and length are
  well-formed).
- The failing send therefore happened in the label→`_analyzePNG` region of
  `main` (source lines 139→20–58). The surviving source's sends there are
  exclusively compile-time: `pixelsHigh`, `pixelsWide`,
  `getPixel:atX:y:`, `appendString:`, `appendFormat:`, plus the
  `NSLog(@"%@", …)` grid dump. The timing (~2.5 s in, after ~1 s runloop +
  capture + PNG load ≈ when the per-pixel loop starts) is most consistent
  with the failure landing on `getPixel:atX:y:` inside `_analyzePNG`, but
  the report alone cannot attribute the exact send: msgSend stubs and
  forwarding trampolines carry no unwind frames, so the unwinder collapses
  the chain straight to `main`, and the recorded frame value `0x13c8` is a
  few instructions off both neighbouring return addresses (`0x13bc`,
  `0x13cc`) — an unresolved ±few-instruction unwinding artifact, flagged
  open.
- **No dynamic-selector machinery exists anywhere in the app code.** The
  surviving build scans: zero `bl _objc_msgSend` direct calls (every send
  routes through a fixed `objc_msgSend$<selector>` stub); zero
  `NSSelectorFromString` / `sel_registerName` / `performSelector`; 61
  stubs ↔ 61 `__objc_methname` names in exact bijection; ZERO occurrences
  of the byte sequence `%s\0` anywhere in the file; no `%` in any
  methname. The crash-region listing is byte-identical between the crashed
  build and the surviving build (re-listed on both). The surviving source
  (post-crash edits 13:54:31/13:54:41) contains no printf-family calls.
- The timeline rules out a rebuild-between-crashes: binary mtime 13:53:47
  (verified 13:54:33) is older than both launches; the 13:54:38 incident's
  `slice_uuid` is again `508cf4a6`.

Interpretation (hypotheses — labeled, not proven):

- **H1 (leading): one-off bad selector binding in the rapid ad-hoc
  rebuild loop.** The failing message's selector register resolved at load
  to a non-selector C string (a `%s\0` printf-fragment in some loaded
  image, most plausibly a system framework's `__cstring`) instead of the
  interned selector; forwarding interned/raised `%s`. Consistent with:
  valid receiver, no dynamic-selector code, no `%s\0` bytes in the app
  binary, and non-reproduction on the rebuild whose crash-region code is
  byte-identical. Also predicts the *same* selector name for any sibling
  binary bitten by the same mis-bind — which matches `inktest7`
  (different binary, same day, same build loop, same literal `%s`
  selector, different receiver/offset).
- **H2 (variant of H1):** the same mechanism with the locus at dyld's
  chained-fixup binding time rather than the linker's — a single selector
  rebase bound to the wrong target. Same predictions; same evidence state.
- **H3 (kept open, weakest):** transient runtime memory corruption
  overwrote a selector-relevant pointer (GOT/selref slot or interned
  selector name) mid-run ~2.5 s in. Fits the crash-in-hot-loop timing but
  offers no other corruption signature (single frame affected, no
  allocator diagnostics in the report).
- **Weakened predecessor hypothesis:** the primary hypothesis recorded in
  the `inktest7` report ("the crashed iteration built a selector
  dynamically, e.g. via `NSSelectorFromString` or a `char *` cast") is
  now **weakened** by this issue: `inktest8`'s crashed build provably
  contained no dynamic-selector code and no `%s` bytes, yet shows the
  identical `%s`-selector signature. Revisit `inktest7`'s Analysis if
  convenient — the shared signature now points at a build/load-time
  selector-binding fault in the rapid rebuild loop rather than a
  source-level idiom.
- **Decisive experiment for the next live occurrence** (do it *before* the
  build is overwritten): attach without launching the target under the
  debugger (`screencapture` fails under a launched lldb) —
  `lldb -p <pid>` right after launch, then
  `break set -n _CF_forwarding_prep_0` (and/or
  `break set -S doesNotRecognizeSelector:`), continue, and on the hit read
  `register read x0 x1`, `expr (const char*)$x1`, and
  `image lookup -a $x1` — that identifies both the exact failing send and
  which image the bogus selector pointer lands in.

## Impact and workaround

- Impact: development-only; the tool aborted on 2/2 runs of the crashed
  build before producing its analysis output. No data loss (read-only
  input PDF plus the tool's own scratch PNGs).
- Workaround: in-place — the dev rebuilt 13:54:44 (`92179863-…`,
  crash-region code unchanged); the surviving build binds selectors
  correctly (exact stub/methname bijection, no `%s` bytes) and completed
  cleanly on the 14:00:57 verification run. Keep every message send
  compile-time (already true); record a few more clean dev-loop runs to
  move this entry to `resolved`.

## Upstream report

- Where: N/A — first-party tool; the only plausible non-local locus (H2,
  dyld chained-fixup binding) has a single incident per binary so far. If
  another tool reproduces the `%s`-selector signature, consider a
  Feedback Assistant report to Apple with both `.ips` files and the
  disassembly evidence.
- Status: not applicable

## Privacy screen (per README policy)

- Both evidence files carry a trailing translated report with a hardware
  network-device serial (Kindle Scribe `<network serial>`, interface en7)
  — the token was replaced with `<REDACTED-SERIAL>` in both copies and
  audited (0 occurrences of the literal after redaction); `diff` confirms
  the evidence files are byte-identical to the originals apart from the
  token. No email addresses, no `/Users/<user>` paths (audit 0);
  `procPath` arrives pre-redacted by Apple as `/Users/USER/*/inktest8`.
- Kept deliberately (pseudonymous): incident ids `1E9FC492-…`,
  `5224214A-…`, slice/build UUID `508cf4a6-…` and `92179863-…`, crash
  reporter key, boot/sleep-wake UUIDs.
- `User ID: 503` is a local POSIX uid.

## Recurrences

One row per later occurrence confirmed by `./check_duplicates.py <new .ips>`
(exit 10; README → "Duplicate / recurrence check"). Same fingerprint means
the same issue — append a row here and commit another `.ips` under
`evidence/`; **never** scaffold a new issue for it. First-party caveat: the
checker cannot distinguish these issues (degenerate fingerprint, shared
with pdfdump/cropzoom/inktest7) — verify the exception reason and build
UUID manually before recording.

| Date | Fingerprint | Incident ID | Evidence file | Note |
|------|-------------|-------------|---------------|------|
| 2026-11-11 (first) | `e3fdfedbc3bc3369` | `1E9FC492-8538-4D48-AD7E-4EAF4275523E` | `inktest8-2026-11-11-135354.ips` | founding crash; build `508cf4a6-…` (binary 13:53:47), pid 31915, launched 13:53:47.74, `%s` on `NSBitmapImageRep` at `main+2544` |
| 2026-11-11 | `e3fdfedbc3bc3369` | `5224214A-A615-4F1E-820D-BC21CE83F58C` | `inktest8-2026-11-11-135440.ips` | same build, same offset `main+2544`, 48 s later; source edited 13:54:31 pre-crash but **no rebuild**; pid 32113 |
