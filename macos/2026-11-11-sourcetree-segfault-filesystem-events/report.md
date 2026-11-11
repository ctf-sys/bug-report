---
date: 2026-11-11
status: open
severity: normal
platform: macOS
component: com.torusknot.SourceTreeNotMAS
---

# Sourcetree SIGSEGV in `objectForKeyedSubscript:` on filesystem_events queue ~33 s after launch

## Summary

Sourcetree 4.2.19 (build 317) crashed at 2026-11-11 02:02:25 +0700, **33
seconds after launch** (02:01:52), with `EXC_BAD_ACCESS (SIGSEGV)` on the
background queue `com.atlassian.sourcetree.filesystem_events`. The faulting
access is a **read at a wild, unmapped address** `0x1d7b6a00078c` —
notably different from a near-NULL dereference. The crash happens inside
`objc_msgSend` invoked from `-[__NSDictionaryM objectForKeyedSubscript:]`,
i.e. while probing a key/value inside an `NSMutableDictionary`. Same boot
session (UUID `1B27F0B7-…`) later produced the unrelated Wacom Center crash
recorded in this repo — different processes and fault signatures.

## Environment

- macOS: 27.2.1 (build 26B131), SIP enabled
- Hardware: Model Identifier `Mac15,3`, Apple M3, 8 GB LPDDR5
- Affected software:
  - Name: Sourcetree
  - Version: 4.2.19 (CFBundleVersion `317`)
  - Bundle: `com.torusknot.SourceTreeNotMAS` (signing team `UPXU4CQZ5P`),
    bundled Sparkle 1.27.3, CocoaLumberjack 3.7.4
  - Install source: vendor download (`/Applications/Sourcetree.app`)
- Reproducibility: once so far, ~33 s after every-launch pipeline start;
  recurrence check pending
- State at observation: 280 s awake since boot; app launched 02:01:52,
  captured 02:03:36 (Role: Background, launchd parent)

## Observed debug messages

Source: macOS crash reporter `.ips` (bug_type 309). Verbatim excerpt from
the crashed thread (15) and its registers:

```
Triggered by Thread: 15, Dispatch Queue: com.atlassian.sourcetree.filesystem_events

Exception Type:    EXC_BAD_ACCESS (SIGSEGV)
Exception Subtype: KERN_INVALID_ADDRESS at 0x00001d7b6a00078c

Thread 15 Crashed::  Dispatch queue: com.atlassian.sourcetree.filesystem_events
0   libobjcMsgSend.dylib           0x19174c808 objc_msgSend + 8
1   CoreFoundation                 0x18de5dcfc -[__NSDictionaryM objectForKeyedSubscript:] + 164
2   Sourcetree                     0x10095fb34 0x100794000 + 1882932
3   libdispatch.dylib              _dispatch_call_block_and_release + 32
...

Thread 15 crashed with ARM Thread State (64-bit):
    x0:  0x00001d7b6a00078c   (== far: the faulted address; msgSend receiver)
    x1:  0x00000001fe70ecd0   (symbolized: objc-selector "isEqual:")
    fp:  0x000000016fe9aa70   lr:  0x000000018de5dcfc
    far: 0x00001d7b6a00078c
    esr: 0x92000005 (Data Abort) byte read Translation fault

VM Region Info: 0x1d7b6a00078c is not in any region.
      UNUSED SPACE AT START  --->  UNUSED SPACE AT END
```

Supporting registers symbolized by the crash reporter: an
`OBJC_CLASS_$_NSObject` reference and **`___NSDictionaryM_DeletedMarker`** —
the tombstone used by mutable dictionaries after entry removal.

Evidence files:

- `evidence/Sourcetree-2026-11-11-020336.ips` — full report (translated
  header + JSON body + trailing system profile), one token redacted (see
  Privacy screen).

## Collection commands used

```sh
ls -lt ~/Library/Logs/DiagnosticReports | head -20
# .ips (bug_type 309) captured automatically; copied verbatim (1 redaction)
```

## Steps to reproduce

1. Launch Sourcetree; on the observed incident the crash followed ~33 s
   after launch while startup repository scanning runs.
2. Repeat launches; record time-to-crash from the next `.ips` in
   `~/Library/Logs/DiagnosticReports`.
3. Correlate with what the UI/index had started doing (repo list render,
   FSEvents scan) at that moment.

## Expected vs actual

- Expected: background filesystem-event pipeline keeps running.
- Actual: SIGSEGV on a worker thread of the pipeline; process terminated.

## Analysis

Observed facts:

- Thread 15 executed a dispatch block on
  `com.atlassian.sourcetree.filesystem_events` running Sourcetree code
  (unsymbolicated, offset 1882932) that called
  `objectForKeyedSubscript:` on a mutable dictionary, which ended in
  `objc_msgSend(receiver = x0 = 0x1d7b6a00078c, selector = isEqual:)`.
- The receiver address is **unmapped** and equals the faulting address:
  the "key" being probed was not a valid object pointer at that moment.
- The dictionary state contains the `___NSDictionaryM_DeletedMarker`
  tombstone — an entry had been deleted from the dictionary.
- Thread 16 was concurrently active **on the same named queue**, in
  adjacent Sourcetree code (offsets 1881532 and 1882304), inside
  `-[NSString rangeOfString:options:range:locale:]` /
  `CFStringFindWithOptionsAndLocale`.

Interpretation (hypothesis — labeled, not proven):

- Shape matches a **use-after-free of a dictionary key** on a shared
  `NSMutableDictionary`: the key was deallocated (possibly by a concurrent
  mutation — `DeletedMarker` visible) while lookup called
  `isEqual:` on its stale pointer, now garbage.
- Two threads active simultaneously on the same named queue is itself
  anomalous for a serial queue; both frame pointers sit in the same code
  region (~offset 1.88 MB), so a concurrent filesystem-event processing
  function operating on shared mutable state (dictionary + path strings)
  is the strongest single explanation.
- Alternative to keep open: single-threaded logic error retaining a
  freed key in a cached dictionary (no race required). Distinguishing
  needs recurrence + a symbolicated backtrace (below).
- Timing note: crash occurs during the post-launch scan, consistent with
  the first burst of FSEvents work.

Symbolication (build UUID `78a1482c-e510-3cb2-8377-0519aee14fcf`):

```sh
atos -arch arm64 \
  -o /Applications/Sourcetree.app/Contents/MacOS/Sourcetree \
  -l 0x100794000 0x10095fb34 0x10095f5bc 0x10095f8c0
```

(covers the crashed frame and both thread-16 frames, which likely land in
the same method family; compare with the Wacom entry's dedup caveat:
this report has real symbols only for system frames — all Sourcetree
frames are offsets.)

## Impact and workaround

- Impact: Sourcetree process aborted once during startup scanning; no
  data loss indicated by the report; recurrence would make the app
  unusable until mitigated.
- Workaround: relaunch Sourcetree; if it becomes recurring, try disabling
  repository auto-scan/watching as a mitigation (untested — record result).

## Upstream report

- Where: not filed yet — candidate: Atlassian Sourcetree issue tracker,
  attaching `incident_id A1F48A04-FC9C-4723-A906-5FB1503C1954` and slice
  UUID `78a1482c-e510-3cb2-8377-0519aee14fcf`.
- Status: not filed

## Privacy screen (per README policy)

- **Redacted one device serial**: the trailing system profile identifies
  a USB gadget as `Kindle Scribe <REDACTED-SERIAL>` (`en7`). The serial
  token was replaced in the evidence copy; the line is otherwise verbatim.
- Scanned for email / username / home-paths / SSID / tokens: none present.
- Kept deliberately (pseudonymous): incident id, slice UUID,
  crash reporter key, sleep/wake UUID, `deviceIdentifierForVendor`,
  signing team ID, BootROM/OS build strings.
- `User ID: 503` is a local POSIX uid.
