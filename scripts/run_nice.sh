#!/usr/bin/env bash
set -euo pipefail

THRESHOLD_MB=1536

log() {
  echo "[run_nice] $*"
}

quick_mem_line() {
  if command -v free >/dev/null 2>&1; then
    free -h 2>/dev/null | tr '\n' ';'
    return 0
  fi

  if command -v vm_stat >/dev/null 2>&1; then
    vm_stat 2>/dev/null | tr '\n' ';'
    return 0
  fi

  echo "n/a"
}

quick_meminfo_line() {
  if [ -r /proc/meminfo ]; then
    grep -E 'MemAvailable|SwapTotal|SwapFree' /proc/meminfo 2>/dev/null | tr '\n' ';'
    return 0
  fi

  echo "n/a"
}

mem_available_mb() {
  # Linux path
  if [ -r /proc/meminfo ]; then
    awk '/MemAvailable:/ {printf "%d\n", $2/1024; found=1} END {if (!found) print -1}' /proc/meminfo
    return 0
  fi

  # macOS fallback (rough estimate: free + inactive pages)
  if command -v vm_stat >/dev/null 2>&1; then
    local pagesize free_pages inactive_pages
    pagesize="$(sysctl -n hw.pagesize 2>/dev/null || echo 4096)"
    free_pages="$(vm_stat 2>/dev/null | awk -F: '/Pages free/ {gsub(/[^0-9]/,"",$2); print $2+0}')"
    inactive_pages="$(vm_stat 2>/dev/null | awk -F: '/Pages inactive/ {gsub(/[^0-9]/,"",$2); print $2+0}')"
    free_pages="${free_pages:-0}"
    inactive_pages="${inactive_pages:-0}"
    echo $(( ( (free_pages + inactive_pages) * pagesize ) / 1024 / 1024 ))
    return 0
  fi

  echo -1
}

oom_diagnostics() {
  log "oom_diag_start"

  if command -v dmesg >/dev/null 2>&1; then
    dmesg -T 2>/dev/null | egrep -i 'oom|out of memory|killed process' | tail -n 50 || true
  fi

  if command -v journalctl >/dev/null 2>&1; then
    journalctl -k --no-pager 2>/dev/null | egrep -i 'oom|out of memory|killed process' | tail -n 50 || true
  fi

  log "oom_diag_end"
}

run_soft_limited() {
  if command -v ionice >/dev/null 2>&1 && command -v nice >/dev/null 2>&1; then
    ionice -c2 -n7 nice -n 10 "$@"
    return
  fi

  if command -v nice >/dev/null 2>&1; then
    nice -n 10 "$@"
    return
  fi

  "$@"
}

if [ "$#" -eq 0 ]; then
  log "ERROR: no command provided"
  exit 2
fi

log "ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
log "uptime=$(uptime -p 2>/dev/null || uptime 2>/dev/null || echo n/a)"
log "mem=$(quick_mem_line)"
log "meminfo=$(quick_meminfo_line)"
log "disk=$(df -h / 2>/dev/null | tail -n 1 || echo n/a)"

avail_mb="$(mem_available_mb)"
if [ "$avail_mb" -ge 0 ] 2>/dev/null; then
  log "mem_available_mb=${avail_mb}"
  if [ "$avail_mb" -lt "$THRESHOLD_MB" ]; then
    log "WARN: low MemAvailable (< ${THRESHOLD_MB}MB). Run may be unstable / OOM-prone."
  fi
else
  log "mem_available_mb=unknown"
fi

set +e
run_soft_limited "$@"
rc=$?
set -e

log "post_uptime=$(uptime -p 2>/dev/null || uptime 2>/dev/null || echo n/a)"
log "post_mem=$(quick_mem_line)"
log "post_meminfo=$(quick_meminfo_line)"
log "post_disk=$(df -h / 2>/dev/null | tail -n 1 || echo n/a)"

if [ "$rc" -ne 0 ]; then
  log "WARN: command failed rc=${rc}"
  oom_diagnostics
  exit "$rc"
fi

log "done rc=0"
exit 0
