# bug-report

Personal record of software bugs found on machines I maintain.
Most issues originate from **macOS debug messages** (unified log,
crash/hang reports); Android ROM issues occasionally.

## Layout

```
README.md                       # this file + issue index table
new-issue.sh                    # scaffold a new issue from a template
check_duplicates.py             # deterministic .ips duplicate/recurrence check
templates/
  macos-issue.md                # macOS report template
  android-issue.md              # Android report template
  log-collection-macos.md       # macOS diagnostics collection cheat sheet
macos/
  <YYYY-MM-DD>-<slug>/          # one directory per issue
    report.md
    evidence/                   # raw logs, crash/hang reports (sanitized)
android/
  <YYYY-MM-DD>-<slug>/
    report.md
    collection.md               # commands used to collect evidence
    evidence/
```

## Workflow

1. For a macOS crash, run `./check_duplicates.py <new .ips>` **first** (see
   "Duplicate / recurrence check" below) — exit 10/11 means record a
   recurrence in the existing issue instead of scaffolding.
2. Run `./new-issue.sh macos "<kebab-slug>"` (or `android`) — creates the
   directory, `report.md` from the template, and `evidence/`.
3. Fill in the front matter (status, severity, component) and the sections:
   summary, environment, observed debug messages, reproduction, analysis.
4. Save raw evidence under `evidence/`. Keep the original filenames
   (macOS `.ips`/dump names already carry dates and hostnames).
5. Paste exact log excerpts with their timestamps in `report.md`, together
   with the `log show`/`log stream` command that produced them — without the
   command, an excerpt is impossible to reproduce or extend later.
6. Add a row to the index table below.
7. Commit. Keep report.md the source of truth; move resolved items only
   after recording the outcome.

## Duplicate / recurrence check (deterministic)

`./check_duplicates.py <new-report.ips>` decides by fixed rules whether a
fresh macOS crash is already recorded here. Stdlib-only Python, no network,
no AI: identical input always yields the identical verdict.

Fingerprint compared per evidence file (raw fault addresses are never
compared directly — ASLR re-randomizes them on every run):

- app bundle `CFBundleIdentifier`
- app binary **build UUID** — pins the exact build of the crashing binary
- exception kind: type + signal + subtype (hex addresses normalized to
  `0xADDR`) + address class `near-null` (< 0x100000) vs `wild`
- top-3 `imageOffset`s of the app's own frames on the faulting thread, in
  stack order — stable across runs within one build
- faulting dispatch queue

Same bundle + same build UUID + same kind + same top offsets + same queue
⇒ RECURRENCE. Same kind but shifted offsets or a different build ⇒
POSSIBLE (human review; a new build usually shifts frame offsets).

| Exit | Verdict | Action |
|------|---------|--------|
| 0 | clean (or same app, different shape) | file a new issue normally |
| 10 | RECURRENCE | record in the existing issue: sanitize the new `.ips` into its `evidence/`, append a row to its `## Recurrences` table — do **not** scaffold |
| 11 | POSSIBLE | review manually first (if the build changed, re-symbolicate with `atos`); then T1-style update or a new issue |
| 3 | unparsable input | check did not run — classify manually |
| 2 | usage error | fix arguments |

`--scan-all` cross-checks every committed `evidence/*.ips` pairwise (catches
issues that are duplicates of each other); `--verbose` prints the extracted
signatures. Feeding an already-committed evidence file back flags itself —
that is the intended sanity check. Scope: macOS `.ips` with a JSON `threads`
body (crash and hang reports); Android issues are compared manually.

## Naming and status vocabulary

- Directory name: `YYYY-MM-DD-<kebab-case-slug>` where the date is the
  first observation. Do not rename after creation (stable references).
- Status: `open` → `investigating` → `reported` (upstream) → `resolved`
  or `wontfix`.
- Severity: `blocker` (system unusable / reboots), `major` (feature broken,
  workaround missing), `normal` (workaround exists), `minor`.

## macOS log sources (quick reference)

Full commands: see `templates/log-collection-macos.md`.

| Source | Path / command |
|--------|----------------|
| Unified log (historical) | `log show --start ... --end ... --predicate '...'` |
| Unified log (live) | `log stream --level debug` |
| Crash reports (.ips) | `~/Library/Logs/DiagnosticReports/`, `/Library/Logs/DiagnosticReports/` |
| Hang reports | `HANG_*.ips`, `cpu_info_*.hdrop` in the same directories |
| Process sample | `sample <pid> 10 -file out.txt` |
| System-wide sample | `sudo spindump -notarget <out-file>` |
| Kernel/panic | `Kernel_*.panic` in DiagnosticReports; `log show --predicate 'processID == 0'` |
| Power/sleep history | `pmset -g log` |

## Security and privacy (read before committing evidence)

- This repository is **public**. macOS logs and crash reports routinely
  contain email addresses, usernames, home-directory paths, device serial
  numbers, MAC addresses, SSIDs and sometimes OAuth/bearer tokens.
  Sanitize before committing: excerpt narrowly, and redact with
  `sed -E 's/(pattern)/REDACTED/g'` when the surrounding lines still matter.
- Prefer excerpts of 3–20 relevant lines in `report.md`; trim raw dumps in
  `evidence/` with `grep`/`sed` instead of committing full sysdiagnose
  archives (hundreds of MB, and far too sensitive).
- Audit rule of thumb used for existing evidence: search for
  `[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}`, `serial`, `imei`, `token`,
  `password` before pushing — and confirm matches are real data, not API
  symbols (e.g. `apex@com.android.*` is a package path, not an email).

## Deletion / history notes

- **2026-11-11 — privacy purge:** raw Android ANR dumps (2026-09-12,
  ~1.8 MB, 2 files) deleted from the working tree **and all git history**
  via `git filter-repo --invert-paths` + force push, after a full PII audit
  of their contents (audit found no real personal data — removed as stale
  bulk evidence; `report.md`/`collection.md` retain the analysis).
  Old commit hashes from before this date are invalid; refer to content by
  current paths only.
- **2026-11-11 — commit identity:** `kubectf@gmail.com` removed from commit
  metadata; all commits now use
  `73512546+ctf-sys@users.noreply.github.com` (GitHub noreply form), and
  repo-local `user.email` is set to the same so future commits stay clean.
- GitHub may retain cached views of force-pushed content until their
  Support purges it; any external clones/forks made earlier still hold the
  old data. Treat the removal as best-effort at the platform level.

## Index

| First seen | Platform | Issue | Affected | Status | Note |
|------------|----------|-------|----------|--------|------|
| 2026-09-12 | Android 16 (SM-N970F/d1, Evolution X 11.9) | [Kindle triggers StorageManagerService/vold watchdog → reboot](android/2026-09-12-d1-kindle-vold-watchdog/report.md) | `com.amazon.kindle` 8.156.0.100 | open | `system_server` watchdog; not a normal ANR; raw ANR dumps purged from history 2026-11-11 |
| 2026-11-11 | macOS 27.2.1 (Mac15,3) | [Wacom Center SIGSEGV on main-thread polling timer ~4 s after wake](macos/2026-11-11-wacom-center-segfault-after-wake/report.md) | `com.wacom.WacomCenter` 6.4.14-1 (6.4.14f1) | open | `EXC_BAD_ACCESS @0x10` from `-[MainWindowDelegate pollingTimerCallback:]`; wake-correlated |
| 2026-11-11 | macOS 27.2.1 (Mac15,3) | [Sourcetree SIGSEGV in dict lookup on filesystem_events queue ~33 s after launch](macos/2026-11-11-sourcetree-segfault-filesystem-events/report.md) | `com.torusknot.SourceTreeNotMAS` 4.2.19 (317) | open | wild read via `objc_msgSend isEqual:` under `objectForKeyedSubscript:`; suspected UAF on shared dictionary |
