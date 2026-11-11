# bug-report

Personal record of software bugs found on machines I maintain.
Most issues originate from **macOS debug messages** (unified log,
crash/hang reports); Android ROM issues occasionally.

## Layout

```
README.md                       # this file + issue index table
new-issue.sh                    # scaffold a new issue from a template
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

1. Run `./new-issue.sh macos "<kebab-slug>"` (or `android`) — creates the
   directory, `report.md` from the template, and `evidence/`.
2. Fill in the front matter (status, severity, component) and the sections:
   summary, environment, observed debug messages, reproduction, analysis.
3. Save raw evidence under `evidence/`. Keep the original filenames
   (macOS `.ips`/dump names already carry dates and hostnames).
4. Paste exact log excerpts with their timestamps in `report.md`, together
   with the `log show`/`log stream` command that produced them — without the
   command, an excerpt is impossible to reproduce or extend later.
5. Add a row to the index table below.
6. Commit. Keep report.md the source of truth; move resolved items only
   after recording the outcome.

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

## Index

| First seen | Platform | Issue | Affected | Status | Note |
|------------|----------|-------|----------|--------|------|
| 2026-09-12 | Android 16 (SM-N970F/d1, Evolution X 11.9) | [Kindle triggers StorageManagerService/vold watchdog → reboot](android/2026-09-12-d1-kindle-vold-watchdog/report.md) | `com.amazon.kindle` 8.156.0.100 | open | `system_server` watchdog; not a normal ANR |
