---
date: 2026-11-11
status: open
severity: normal
platform: macOS
component: com.wacom.WacomCenter
---

# Wacom Center SIGSEGV in main-thread polling timer ~4 s after wake from sleep

## Summary

Wacom Center 6.4.14-1 crashed with `EXC_BAD_ACCESS (SIGSEGV)` on the main
dispatch queue at 2026-11-11 09:17:43 +0700, **4 seconds after the system
woke from sleep** (`Time Since Wake: 4`). The process had been running
since 02:01 the same morning (890 s of accumulated awake time), so the
correlating event is the sleep→wake transition, not app startup. Observed
once so far. Full crash report: `evidence/Wacom-Center-2026-11-11-091750.ips`.

## Environment

- macOS: 27.2.1 (build 26B131), SIP enabled
- Hardware: Model Identifier `Mac15,3` (ARM-64 native, no translation)
- Affected software:
  - Name: Wacom Center
  - Version: 6.4.14-1 (CFBundleVersion `6.4.14f1`)
  - Bundle: `com.wacom.WacomCenter` at
    `/Applications/Wacom Tablet.localized/Wacom Center.app`
  - Install source: vendor driver bundle (Wacom), signing team `EG27766DY7`
- Reproducibility: once so far — see procedure in "Steps to reproduce"
- State at observation: 890 s awake since boot; 4 s since last wake;
  app launched 02:01:52 same day (Role: Background, launchd parent)

## Observed debug messages

Source: macOS crash reporter `.ips` (bug_type 309), captured
2026-11-11 09:17:50 +0700. Verbatim excerpt:

```
Triggered by Thread: 0, Dispatch Queue: com.apple.main-thread

Exception Type:    EXC_BAD_ACCESS (SIGSEGV)
Exception Subtype: KERN_INVALID_ADDRESS at 0x0000000000000010
Termination Reason:  Namespace SIGNAL, Code 11, Segmentation fault: 11

Thread 0 Crashed::  Dispatch queue: com.apple.main-thread
0   Wacom Center                   0x100a19c60 <deduplicated_symbol> + 0
1   Wacom Center                   0x100d9fc94 -[MainWindowDelegate pollingTimerCallback:] + 112
2   Foundation                     0x18a3a3450 __NSFireTimer + 104
3   CoreFoundation                 0x18deb78a8 __CFRUNLOOP_IS_CALLING_OUT_TO_A_TIMER_CALLBACK_FUNCTION__ + 32
4   CoreFoundation                 0x18deb75a4 __CFRunLoopDoTimer + 1084
5   CoreFoundation                 0x18deb70b4 __CFRunLoopDoTimers + 280
6   CoreFoundation                 0x18de9c5b8 __CFRunLoopRun + 1852

VM Region Info: 0x10 is not in any region.  Bytes before following region: 4305551344
      UNUSED SPACE AT START
--->  __TEXT 100a18000-101104000  [ 7088K] r-x/r-x SM=COW  .../Wacom Center

Thread 0 crashed with ARM Thread State (64-bit):
    x0:  0x0000000000000010   x17: 0x0000100000000000
    x16: 0x000000018ecaf620  (symbolized: std::__1::basic_string<char...>::~basic_string())
    far: 0x0000000000000010
    esr: 0x92000006 (Data Abort) byte read Translation fault
```

Evidence files:

- `evidence/Wacom-Center-2026-11-11-091750.ips` — full report (translated
  header + JSON body), copied verbatim.

## Collection commands used

```sh
ls -lt ~/Library/Logs/DiagnosticReports | head -20
# .ips (bug_type 309) captured automatically by the macOS crash reporter;
# copied verbatim into evidence/ (filename normalized for shell use)
```

## Steps to reproduce

Not reproducible on demand yet. Correlation to document/verify:

1. Leave Wacom Center running; let the machine sleep.
2. Wake; within seconds check `~/Library/Logs/DiagnosticReports` for a new
   `Wacom Center-*.ips`.
3. Repeat for several sleep/wake cycles; note whether every wake crashes or
   only some.
4. During the wake window, capture `log stream --process "Wacom Center"
   --level debug` to see what the polling timer touches.

Do not claim "always on wake" until (3) shows a pattern.

## Expected vs actual

- Expected: background process survives sleep/wake cycles; polling timer
  re-establishes device state.
- Actual: SIGSEGV on the first timer tick after waking; process terminated
  by the exception handler.

## Analysis

Observed facts:

- Crashed on thread 0 (main run loop) inside a Foundation timer callback:
  frame 1 is `-[MainWindowDelegate pollingTimerCallback:]`, invoked from
  `__NSFireTimer` (frame 2). The main RunLoop was otherwise healthy:
  NSEventThread (thread 1) sat in `mach_msg`, auxiliary threads idle.
- The faulting access is a **read** at `0x10` (`far = 0x10`, esr
  `Data Abort, byte read, Translation fault`), and `x0 = 0x10`. VM Region
  Info confirms `0x10` is unmapped (NULL page area) — this is a near-NULL
  dereference, not a wild heap pointer.
- Frame 0 is a native symbol at imageOffset 7264 — within the first code
  page of the binary. The report symbolizes register `x16` as
  `std::__1::basic_string<char...>::~basic_string()`, i.e. the crashed code
  is C++ (libc++), and the timer callback dispatches into a C++ helper.

Interpretation (hypothesis — labeled, not verified):

- Shape `x0 = 0x10` with a read at `+0x10` is consistent with a member
  access (offset +0x10) on a **NULL or already-destroyed object treated as
  `this`** in C++ code reached from `pollingTimerCallback:`. An ObjC nil
  message send would not fault like this; passing a nil/garbage pointer
  into a C++ function would.
- Wake-from-sleep correlation: the timer fired seconds after wake. A
  polling timer that probes the tablet/plug-in status is a plausible owner
  of state that is stale or not yet reconnected immediately after wake.
  This is the most likely trigger but is not proven by the report alone.

Symbolication note: `<deduplicated_symbol>` means Apple's reporter collapsed
identically-shaped frames. Exact attribution offline needs the **exact build
** (UUID `7140ed6a-fdf8-3ff2-8983-55017163c870`) of the binary:

```sh
atos -arch arm64 \
  -o "/Applications/Wacom Tablet.localized/Wacom Center.app/Contents/MacOS/Wacom Center" \
  -l 0x100a18000 0x100a19c60 0x100d9fc94
```

(load address `0x100a18000` and faulting PCs from the report; the JSON body
also contains `instructionByteStream` around PC for offline disassembly.)

## Impact and workaround

- Impact: the Wacom Center control panel process aborted once; no data
  loss; tablet driver components outside this UI are unaffected by this
  report's evidence.
- Workaround: relaunch Wacom Center when it disappears after waking.

## Upstream report

- Where: not filed yet — candidate: Wacom support, attaching
  `incident_id 4D383018-351F-4B0A-8450-9BA7CEDA1154` and slice UUID
  `7140ed6a-fdf8-3ff2-8983-55017163c870`.
- Status: not filed

## Privacy screen (per README policy)

- Scanned for email / username / home-path / serial / SSID / token
  patterns: **none present** in this report.
- Kept deliberately (pseudonymous, needed by support and for symbol
  verification): incident id, slice UUID, crash reporter key, sleep/wake
  UUID, `deviceIdentifierForVendor`, signing team ID.
- `User ID: 503` is a local POSIX uid; `Hardware Model Mac15,3` is a model
  identifier, not a serial number.
