#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SERVE_BASE_URL="${SERVE_BASE_URL:-http://127.0.0.1:8901}"
CHAT_URL="${CHAT_URL:-${SERVE_BASE_URL}/v1/chat/completions}"
HEALTH_URL="${HEALTH_URL:-${SERVE_BASE_URL}/health}"
OUT_DIR="${OUT_DIR:-data/evals}"
MAX_TOKENS="${MAX_TOKENS:-64}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_PATH="${OUT_DIR}/serve_smoke_${TS}.txt"

mkdir -p "${OUT_DIR}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $1" >&2
    exit 2
  }
}

normalize_text() {
  # Normalize whitespace/newlines to make exact checks deterministic.
  printf '%s' "$1" \
    | tr '\r' '\n' \
    | sed -E ':a;N;$!ba;s/[[:space:]]+/ /g;s/^ +//;s/ +$//'
}

has_wrapper_leak() {
  # Returns 0 if leak found, 1 otherwise.
  # Blocking known template/wrapper artifacts.
  local text_lc
  text_lc="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  if printf '%s' "${text_lc}" | grep -qE '### *input:|### *response:|### *instruction:'; then
    return 0
  fi
  if printf '%s' "${text_lc}" | grep -qE '(^|[[:space:]])(kontext:|antwort:|instruction:|aufgabe:|regel:)'; then
    return 0
  fi
  return 1
}

log() {
  printf '%s\n' "$1" | tee -a "${REPORT_PATH}" >/dev/null
}

require_cmd curl
require_cmd jq
require_cmd sed
require_cmd grep
require_cmd tr
require_cmd mktemp

: > "${REPORT_PATH}"
log "serve_smoke_ts_utc=${TS}"
log "serve_base_url=${SERVE_BASE_URL}"
log "chat_url=${CHAT_URL}"
log "health_url=${HEALTH_URL}"
log "report_path=${REPORT_PATH}"
log ""

health_tmp="$(mktemp)"
health_http="$(curl -sS -m 20 -o "${health_tmp}" -w "%{http_code}" "${HEALTH_URL}" || true)"
health_body="$(cat "${health_tmp}")"
rm -f "${health_tmp}"

log "health_http=${health_http}"
log "health_body=${health_body}"
log ""

if [ "${health_http}" != "200" ]; then
  log "RESULT=FAIL"
  log "reason=health_not_reachable_or_not_200"
  exit 1
fi

health_status="$(printf '%s' "${health_body}" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")"
if [ "${health_status}" != "ok" ]; then
  log "RESULT=FAIL"
  log "reason=service_not_ready status=${health_status}"
  exit 1
fi

# Standardized test cases:
# id|prompt|expected_exact
CASES=(
  "serve-001|Nenne den Pfad zur compose Datei für serving.|docker/compose.serve.yaml"
  "serve-002|Gib mir nur den exakten Befehl für make preflight.|make preflight"
  "serve-003|Antworte exakt mit einem Wort: OK|OK"
)

total=0
passed=0
failed=0

for row in "${CASES[@]}"; do
  total=$((total + 1))
  IFS='|' read -r case_id prompt expected <<<"${row}"

  payload="$(jq -n \
    --arg p "${prompt}" \
    --argjson max_tokens "${MAX_TOKENS}" \
    '{
      model: "local",
      messages: [{role:"user", content:$p}],
      temperature: 0.0,
      max_tokens: $max_tokens
    }'
  )"

  resp_tmp="$(mktemp)"
  http_code="$(curl -sS -m 60 -o "${resp_tmp}" -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -d "${payload}" \
    "${CHAT_URL}" || true)"

  body="$(cat "${resp_tmp}")"
  rm -f "${resp_tmp}"

  content="$(printf '%s' "${body}" | jq -r '.choices[0].message.content // empty' 2>/dev/null || true)"
  norm_content="$(normalize_text "${content}")"
  norm_expected="$(normalize_text "${expected}")"

  case_ok=true
  reason="ok"

  if [ "${http_code}" != "200" ]; then
    case_ok=false
    reason="http_${http_code}"
  elif [ -z "${content}" ]; then
    case_ok=false
    reason="empty_content"
  elif has_wrapper_leak "${content}"; then
    case_ok=false
    reason="wrapper_leak_detected"
  elif [ "${norm_content}" != "${norm_expected}" ]; then
    case_ok=false
    reason="semantic_mismatch"
  fi

  if [ "${case_ok}" = true ]; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
  fi

  log "case_id=${case_id}"
  log "prompt=${prompt}"
  log "expected=${expected}"
  log "http=${http_code}"
  log "content=${content}"
  log "normalized_content=${norm_content}"
  log "normalized_expected=${norm_expected}"
  log "case_result=$([ "${case_ok}" = true ] && echo PASS || echo FAIL)"
  log "case_reason=${reason}"
  log ""
done

log "summary_total=${total}"
log "summary_passed=${passed}"
log "summary_failed=${failed}"

if [ "${failed}" -gt 0 ]; then
  log "RESULT=FAIL"
  exit 1
fi

log "RESULT=PASS"
exit 0
