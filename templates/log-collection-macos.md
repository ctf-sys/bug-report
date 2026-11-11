# macOS diagnostics collection cheat sheet

Commands verified on recent macOS. Replace `<pid>`, `<name>`, timestamps and
predicates as needed. All output goes under `evidence/` after sanitization.

## System facts

```sh
sw_vers                                        # ProductVersion + BuildVersion
system_profiler SPHardwareDataType             # model, chip, memory, serial(!)
system_profiler SPApplicationsDataType \
  | grep -B4 -A2 '<name>'                      # app version + install source
uptime
```

## Unified log

```sh
# Historical window — use precise start/end to keep the file small
log show --start '<YYYY-MM-DD HH:MM:SS>' --end '<YYYY-MM-DD HH:MM:SS>' \
  --predicate 'process == "<name>"' \
  --style syslog > evidence/<name>-unified.log

# Multiple conditions; level filtering (16=default, 17=info/debug range)
log show --last 1h \
  --predicate 'process == "kernel" AND eventMessage CONTAINS "sleep"'

# Per-subsystem, with debug level included
log show --last 30m --level debug \
  --predicate 'subsystem == "com.apple.<subsystem>"'

# Live capture while reproducing
log stream --level debug \
  --predicate 'process == "<name>"' \
  --style compact > evidence/<name>-stream.log
```

Tips: `log show --last 1h --info --debug` for full detail; extract only the
lines you cite in report.md; `--signpost` data for performance issues.

## Crash and hang reports (.ips)

```sh
ls -lt ~/Library/Logs/DiagnosticReports | head -20
ls -lt /Library/Logs/DiagnosticReports | head -20

# .ips format: header JSON line + body JSON (or legacy text). Extract core:
tail -n +2 <name>-PID.ips \
  | jq -r '.faultingThread, .exception, .terminationReason' 2>/dev/null
```

Hang detection artifacts: `HANG_*.ips`, `cpu_info_*.hdrop` in the same
directories — usually the best evidence for "app beachballs" reports.

## Sampling a running process

```sh
sample <pid> 10 -file evidence/<name>-sample.txt        # one process
sudo spindump -notarget 10 -file evidence/spindump.txt  # whole system, needs sudo
```

## Kernel, power, storage

```sh
pmset -g log | grep -E "Sleep|Wake|Failure"    # sleep/wake/failure history
log show --last 24h --predicate 'processID == 0' \
  --style syslog > evidence/kernel.log         # kernel-level events
ls -l /Library/Logs/DiagnosticReports/Kernel_*.panic   # panic reports
```

## sysdiagnose (last resort)

```sh
sudo sysdiagnose -f                            # produces a large archive in /var/tmp
```

Do **not** commit sysdiagnose archives: extract only the individual reports
you cite, then sanitize them.

## Sanitization before committing

```sh
# Screen for common PII first
grep -inE '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|serial|imei|token|password|ssid' \
  evidence/*

# Redact a pattern in place (careful: keep structure)
sed -E 's|/Users/[^/]+|/Users/REDACTED|g' evidence/file > evidence/file.clean
```

Remember that `@` matches like `apex@com.android.*` or `foo@2x` can be false
positives — verify each match is real personal data before editing it.
