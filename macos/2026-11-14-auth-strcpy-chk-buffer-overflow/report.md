---
date: 2026-11-14
status: open
severity: minor
platform: macOS
component: auth (first-party teaching CLI, /private/tmp scratchpad)
---

# auth EXC_BREAKPOINT (SIGTRAP): fortify `__strcpy_chk` aborts a deliberate stack overflow into `login.user[16]` in `main` (1 incident, source-confirmed)

## Summary

`auth`, a 16 KB first-party C program run from an iTerm2 shell (out of a
Claude Code scratchpad for a university course working directory), crashed
**0.15 s after launch** (2026-11-14 09:28:15.098, pid 53930) with:

```
Exception Type:  EXC_BREAKPOINT (SIGTRAP)
Application Specific Information: detected buffer overflow
```

Unlike every earlier issue in this repo, this is not an Apple-framework
exception: the program is a **deliberately vulnerable teaching demo** of
the classic "overflow a buffer to flip the adjacent authorization flag"
exercise —

```c
struct login {
    char user[16];
    int admin;
};
int main(int argc, char *argv[]) {
    struct login s;
    s.admin = 0;
    strcpy(s.user, argv[1]);   /* unbounded copy into a 16-byte field */
    ...
    if (s.admin) printf("ACCESS GRANTED: flag{…}\n");  /* flag redacted */
}
```

— and the crash is the modern toolchain's hardening **working as
designed**: with `_FORTIFY_SOURCE`, the compiler emits `__strcpy_chk(dst,
src, 16)`; the runtime detected `strlen(argv[1]) ≥ 16` and executed
`brk #1` (`__chk_fail_overflow`) **before any bytes landed past the
buffer**, so the very overflow the demo demonstrates is aborted instead of
corrupting `s.admin`. The user re-ran nothing on this build; a successor
binary `auth2` (UUID `1f2e8140-…`) was built 26 s after the crash.

This is the first issue filed against a `/private/tmp` binary and the
first non-Objective-C program in the repo (imports: `___strcpy_chk`,
`_printf` only; no ObjC images loaded). It is unrelated to the
2026-11-11 skim dev-loop series (different boot session
`223898A4-…` vs `1B27F0B7-…`).

## Environment

- macOS: 27.2.1 (build 26B131), SIP enabled, developer mode on
- Hardware: Model Identifier `Mac15,3`, Apple M3, 8 GB LPDDR5
- Affected software:
  - Name: `auth` (single-file C CLI, no bundle identifier, version n/a)
  - Build UUID (crashed build): `aa453a47-c179-4c5a-862d-fa81b0f6c263`
    (verified on disk against the in-session dump: binary and source
    still present at crash time + 1 min)
  - Successor build: `auth2`, UUID `1f2e8140-8a32-4da8-ab93-67aef5a939b1`
    (written 09:28:40, 26 s after the crash; not executed during filing)
  - Install source: compiled locally in a course scratchpad
    (`/private/tmp/…/scratchpad/auth.c`, arm64, ad-hoc signed —
    `codeSigningID: auth`, no team id)
- Reproducibility: 1/1 observed run (launch 09:28:14.9498 → crash
  09:28:15.0985); source + register state confirm the mechanism, so the
  run was deliberately not repeated during filing (avoids emitting the
  course flag / new incidents)
- State at observation: boot session `223898A4-…`; uptime 56000 s;
  launched from iTerm2 (parent process "Exited process" [53923]);

## Observed debug messages

Source: macOS crash reporter `.ips` (bug_type 309). Verbatim excerpt —
the entire backtrace is four frames:

```
Exception Type:    EXC_BREAKPOINT (SIGTRAP)
Exception Codes:   0x0000000000000001, 0x0000000198c34c48
Termination Reason:  Namespace SIGNAL, Code 5, Trace/BPT trap: 5

Application Specific Information:
detected buffer overflow

Thread 0 Crashed::  Dispatch queue: com.apple.main-thread
0   libsystem_c.dylib   0x198c34c48 __chk_fail_overflow + 24
1   libsystem_c.dylib   0x198bc71b4 __strcpy_chk + 108
2   auth                0x1008a4494 main + 52
3   dyld                0x198accd7c start + 6652
```

Register state corroborates the fortify path: `x5 = 0x10` (the 16-byte
destination size in flight) and `esr = 0xf2000001 (Breakpoint) brk 1`.

Evidence file:

- `evidence/auth-2026-11-14-092815.ips` — incident
  `DD7462A2-4E0F-49D5-94B9-4A935D21183F` (pid 53930, founding crash;
  7,659 bytes, header + JSON body only, no trailing system profile)

## Collection commands used

```sh
cp ~/Library/Logs/DiagnosticReports/auth-2026-11-14-092815.ips \
   macos/2026-11-14-auth-strcpy-chk-buffer-overflow/evidence/
./check_duplicates.py --verbose ~/Library/Logs/DiagnosticReports/auth-2026-11-14-092815.ips
# → fp 90a20ddf7ae259ee  auth () queue='com.apple.main-thread' offsets=[1172]
# → RESULT: CLEAN — exit 0  (new issue; see Analysis)
```

The crashed binary and its source were still on disk when the report was
filed, so the analysis below is confirmed at source level and instruction
level, not inferred.

## Steps to reproduce

1. Observed run: `./auth <argument of ≥ 16 bytes>` from an iTerm2 shell
   (launch 09:28:14.9498). The argument length follows from the fortify
   contract — `__strcpy_chk(dst, src, 16)` aborts exactly when
   `strlen(src) + 1 > 16`.
2. Not re-run during filing: the abort path is fully confirmed by the
   `.ips` registers plus the on-disk disassembly, and a re-run would print
   course material (the flag string) into the filing session.
3. The successor build `auth2` (09:28:40) was not executed either;
   whether it disables the fortify check (e.g. `-D_FORTIFY_SOURCE=0`,
   `-fno-builtin`) is unverified.

## Expected vs actual

- Expected by the demo: a long username overflows `user[16]`, overwrites
  the adjacent `admin` int with non-zero bytes, and the program prints its
  ACCESS GRANTED line (the exercise's punchline).
- Actual: `__strcpy_chk` compares the copy against the compile-time
  object size (16), detects the overflow **during** the copy, and
  transfers to `__chk_fail_overflow` → `brk #1` → SIGTRAP. The process
  dies before `s.admin` is touched — memory-safety failure caught at the
  boundary, zero corruption escaped.

## Analysis

Checker verdict: **CLEAN, exit 0** — first-party identity resolved by the
checker's new `slice_uuid` fallback (this binary lives under
`/private/tmp`, not `/Users/…`), fingerprint `90a20ddf7ae259ee`, app-frame
offset `[1172]`. No existing issue shares the executable name or the
exception kind, so no manual-review tier was needed — this is also the
first first-party report filed entirely under the post-2026-11-11 checker
(no exit-11 caveat applies).

Observed facts (source + disassembly + crash state all agree):

- `main` at vaddr `0x100000460`; the crash frame `main + 52` (`0x494`,
  imageOffset 1172) is the instruction **after** `bl ___strcpy_chk` at
  `0x490` — the exact call site:

  ```
  0x100000478  add  x0, sp, #0x1c   ; dst = &s.user   (16-byte field)
  0x100000480  str  wzr, [sp, #0x2c]; s.admin = 0     (adjacent field)
  0x100000484  ldur x8, [x29, #-0x10]
  0x100000488  ldr  x1, [x8, #0x8]  ; src = argv[1]
  0x10000048c  mov  x2, #0x10       ; dstlen = 16 (fortify object size)
  0x100000490  bl   ___strcpy_chk
  0x100000494  ...                  ; ← crash return address (main+52)
  ```

- Struct layout is confirmed by the code: `user` at `sp+0x1c`,
  `admin` at `sp+0x2c` = `0x1c + 16` — the adjacent-field overwrite the
  demo intends is exactly what fortify prevented.
- Binary imports only `___strcpy_chk` and `_printf` (pure C; consistent
  with `usedImages` — no ObjC runtime loaded).
- `auth.c` / `auth` mtimes 09:28:14 (same second as launch);
  `auth2` written 09:28:40. The crashed build's UUID
  (`aa453a47-…`) matches the report's `slice_uuid`.

Conclusion (no hypothesis needed — confirmed): classic unbounded
`strcpy` of `argv[1]` into a 16-byte stack field, caught by
`_FORTIFY_SOURCE`'s `__strcpy_chk` before corruption. The program is
intentionally unsafe; the defect classification here is "hardened libc
aborts a deliberately vulnerable demo", i.e. expected platform behavior,
not a framework bug.

Fix direction for the course demo (not a product fix): build with
`-D_FORTIFY_SOURCE=0` (and/or `-fno-builtin`) so the pedagogical
overwrite can occur — with the usual caution that the demo then behaves
as the exercise expects only under the course's sanctioned conditions;
`auth2` presumably does this (unverified).

## Impact and workaround

- Impact: teaching-material only; one aborted run, no data affected. The
  fortify abort guarantees the overflow never corrupted the stack.
- Workaround: in place — successor binary built 26 s after the crash;
  nothing to resolve in a vendor tracker. Move this entry to `resolved`
  once the course demo runs as intended (or the scratchpad is cleaned).

## Upstream report

- Where: N/A — first-party teaching code; the abort is macOS hardening
  working correctly (`libsystem_c` `__strcpy_chk` / `__chk_fail_overflow`,
  macOS 27.2.1 / 26B131).
- Status: not applicable

## Privacy screen (per README policy)

- The on-disk `.ips` carries **no trailing system profile** (unlike the
  paste used to file this, whose translated profile contains a hardware
  network-device serial): audits over the copied evidence show 0
  occurrences of serial tokens, `/Users/…` paths, scratchpad/course
  paths, or email addresses; the copy is byte-identical to the original
  (no redaction required). `procPath` arrives pre-redacted by Apple as
  `/private/tmp/*/auth`.- The report deliberately does **not** reproduce the course flag string
  found in the source (public repo); the quoted code is limited to the
  vulnerable lines, and the source file itself is not committed.
- Kept deliberately (pseudonymous): incident id `DD7462A2-…`, slice/build
  UUIDs `aa453a47-…` / `1f2e8140-…`, crash reporter key, boot/sleep-wake
  UUIDs.
- `User ID: 503` is a local POSIX uid.

## Recurrences

One row per later occurrence confirmed by `./check_duplicates.py <new .ips>`
(exit 10; README → "Duplicate / recurrence check"). Same fingerprint means
the same issue — append a row here and commit another `.ips` under
`evidence/`; **never** scaffold a new issue for it.

| Date | Fingerprint | Incident ID | Evidence file | Note |
|------|-------------|-------------|---------------|------|
| 2026-11-14 (first) | `90a20ddf7ae259ee` | `DD7462A2-4E0F-49D5-94B9-4A935D21183F` | `auth-2026-11-14-092815.ips` | founding crash; build `aa453a47-…`, pid 53930, `__strcpy_chk` fortify abort at `main+52`; successor `auth2` (`1f2e8140-…`) built 26 s later |
