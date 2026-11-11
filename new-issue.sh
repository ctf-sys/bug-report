#!/bin/sh
# Scaffold a new bug-report issue directory from a template.
# Usage: ./new-issue.sh macos|android <kebab-slug>
# Example: ./new-issue.sh macos "kindle-crash-on-open"
set -eu

platform="${1:-}"
slug="${2:-}"

case "$platform" in
  macos)   tmpl="templates/macos-issue.md" ;;
  android) tmpl="templates/android-issue.md" ;;
  *)
    echo "usage: $0 macos|android <kebab-slug>" >&2
    exit 2
    ;;
esac

[ -n "$slug" ] || {
  echo "$0: missing slug" >&2
  exit 2
}

# kebab-case only: keeps directory names consistent and shell-safe
printf '%s\n' "$slug" | grep -qE '^[a-z0-9]+(-[a-z0-9]+)*$' || {
  echo "$0: slug must be kebab-case ([a-z0-9] joined by '-')" >&2
  exit 2
}

date_now=$(date +%F)
dir="$platform/$date_now-$slug"

if [ -e "$dir" ]; then
  echo "$0: already exists: $dir" >&2
  exit 1
fi

mkdir -p "$dir/evidence"
sed "s/@@DATE@@/$date_now/" "$tmpl" > "$dir/report.md"

echo "created:"
echo "  $dir/report.md"
echo "  $dir/evidence/"
echo "tip (macOS crash): run ./check_duplicates.py <new.ips> first —"
echo "  exit 10/11 = record a recurrence in the existing issue, not a new one"
echo "next: fill in report.md, sanitize logs into evidence/, add an index row in README.md"
