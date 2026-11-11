---
date: @@DATE@@
status: open
severity: normal
platform: macOS
component:
---

# <short, factual title — symptom, not guess>

## Summary

One paragraph: what is happening, since when, how often, and the observable
symptom (crash / hang / reboot / performance / wrong output).

## Environment

- macOS: `<ProductVersion> (<BuildVersion>)` — output of `sw_vers`
- Hardware: `<Model Identifier>, <Chip>, <Memory GB>` — output of
  `system_profiler SPHardwareDataType`
- Affected software:
  - Name:
  - Version:
  - Install source: App Store / Homebrew / vendor pkg / Xcode build
- Reproducibility: always / sometimes / once
- Uptime at the time of observation:

## Observed debug messages

Source: unified log / crash report (.ips) / hang report / kernel / third-party
tool. Paste verbatim lines **with their timestamps**, trimmed to the relevant
window. Mark ellipses explicitly.

```
<paste 3–20 most relevant lines>
```

Report files attached under `evidence/`:

- `evidence/<filename>` — what it shows (one line per file)

## Collection commands used

```
log show --start '<YYYY-MM-DD HH:MM:SS>' --end '<YYYY-MM-DD HH:MM:SS>' \
  --predicate 'process == "<name>" AND eventMessage CONTAINS "<kw>"' \
  --style syslog > evidence/<name>.log
```

## Steps to reproduce

1. ...

## Expected vs actual

- Expected:
- Actual:

## Analysis

Hypotheses and reasoning, citing concrete log lines or stack frames.
Distinguish observed facts from interpretation.

## Impact and workaround

- Impact:
- Workaround:

## Upstream report

- Where: <link>
- Status:

## Recurrences

One row per later occurrence confirmed by `./check_duplicates.py <new .ips>`
(exit 10; README → "Duplicate / recurrence check"). Same fingerprint means
the same issue — append a row here and commit another `.ips` under
`evidence/`; **never** scaffold a new issue for it.

| Date | Fingerprint | Incident ID | Evidence file | Note |
|------|-------------|-------------|---------------|------|
