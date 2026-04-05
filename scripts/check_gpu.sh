#!/usr/bin/env sh
# check_gpu.sh
#
# GPU precondition checks for llm-homelab-training.
# Validates:
#   1) Host NVIDIA stack (driver + GPU visibility)
#   2) Container GPU passthrough + PyTorch CUDA availability
#
# Usage examples:
#   ./scripts/check_gpu.sh
#   ./scripts/check_gpu.sh --host-only
#   ./scripts/check_gpu.sh --container-only
#   ./scripts/check_gpu.sh --compose-file docker/compose.yaml --service trainer
#   ./scripts/check_gpu.sh --min-cc 3.7
#
# Exit codes:
#   0 = all required checks passed
#   1 = one or more required checks failed

set -eu

COMPOSE_FILE="docker/compose.yaml"
SERVICE="trainer"
MIN_CC="3.7"
MODE="all" # all | host | container

PASS_COUNT=0
WARN_COUNT=0

log()  { printf '%s\n' "[INFO] $*"; }
ok()   { PASS_COUNT=$((PASS_COUNT + 1)); printf '%s\n' "[OK]   $*"; }
warn() { WARN_COUNT=$((WARN_COUNT + 1)); printf '%s\n' "[WARN] $*" >&2; }
fail() { printf '%s\n' "[FAIL] $*" >&2; exit 1; }

usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --host-only                Run only host checks.
  --container-only           Run only container checks.
  --compose-file <path>      Docker compose file path (default: ${COMPOSE_FILE}).
  --service <name>           Compose service name (default: ${SERVICE}).
  --min-cc <major.minor>     Minimum compute capability check when detectable (default: ${MIN_CC}).
  -h, --help                 Show help.

Notes:
  - For K80, expected compute capability is 3.7.
  - Container checks require compose service '${SERVICE}' to be running.
EOF
}

version_ge() {
  # Returns 0 if $1 >= $2, else 1
  # Example: version_ge "3.7" "3.5" -> 0
  awk -v a="$1" -v b="$2" 'BEGIN {
    split(a, aa, "."); split(b, bb, ".");
    amaj = (aa[1] == "" ? 0 : aa[1]) + 0;
    amin = (aa[2] == "" ? 0 : aa[2]) + 0;
    bmaj = (bb[1] == "" ? 0 : bb[1]) + 0;
    bmin = (bb[2] == "" ? 0 : bb[2]) + 0;
    if (amaj > bmaj) exit 0;
    if (amaj < bmaj) exit 1;
    if (amin >= bmin) exit 0;
    exit 1;
  }'
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --host-only)
        MODE="host"
        ;;
      --container-only)
        MODE="container"
        ;;
      --compose-file)
        [ "$#" -ge 2 ] || fail "Missing value for --compose-file"
        COMPOSE_FILE="$2"
        shift
        ;;
      --service)
        [ "$#" -ge 2 ] || fail "Missing value for --service"
        SERVICE="$2"
        shift
        ;;
      --min-cc)
        [ "$#" -ge 2 ] || fail "Missing value for --min-cc"
        MIN_CC="$2"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown option: $1"
        ;;
    esac
    shift
  done
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

host_checks() {
  log "Running host GPU checks..."

  require_cmd nvidia-smi

  if ! nvidia-smi >/dev/null 2>&1; then
    fail "nvidia-smi failed on host. Check NVIDIA driver installation."
  fi
  ok "Host nvidia-smi is operational"

  GPU_LIST="$(nvidia-smi -L 2>/dev/null || true)"
  [ -n "$GPU_LIST" ] || fail "No NVIDIA GPUs detected on host"
  ok "Host reports at least one NVIDIA GPU"

  DRIVER_VER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1 || true)"
  [ -n "$DRIVER_VER" ] && ok "Host NVIDIA driver version: ${DRIVER_VER}" || warn "Could not read driver version"

  CUDA_VER="$(nvidia-smi 2>/dev/null | awk -F'CUDA Version: ' '/CUDA Version/ {split($2,a," "); print a[1]; exit}' || true)"
  [ -n "$CUDA_VER" ] && ok "Host CUDA runtime (reported by nvidia-smi): ${CUDA_VER}" || warn "Could not detect CUDA version from nvidia-smi"

  # Optional compute capability check (field may not be available on all nvidia-smi builds)
  CC_LIST="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null || true)"
  if [ -n "$CC_LIST" ]; then
    CC_OK=1
    echo "$CC_LIST" | while IFS= read -r cc; do
      cc_trimmed="$(echo "$cc" | tr -d '[:space:]')"
      if [ -n "$cc_trimmed" ] && version_ge "$cc_trimmed" "$MIN_CC"; then
        :
      else
        CC_OK=0
      fi
    done

    # Re-check without subshell side effects:
    CC_OK_FINAL=1
    for cc in $(echo "$CC_LIST" | tr -d '[:space:]'); do
      if ! version_ge "$cc" "$MIN_CC"; then
        CC_OK_FINAL=0
      fi
    done

    if [ "$CC_OK_FINAL" -eq 1 ]; then
      ok "Host compute capability check passed (>= ${MIN_CC})"
    else
      warn "Some host GPUs appear below minimum compute capability ${MIN_CC}"
    fi
  else
    warn "Host compute capability not detectable via nvidia-smi; skipping CC threshold check"
  fi

  log "Host GPU summary:"
  nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader 2>/dev/null || true
}

container_checks() {
  log "Running container GPU checks..."

  require_cmd docker

  if ! docker compose version >/dev/null 2>&1; then
    fail "Docker Compose plugin unavailable"
  fi
  ok "Docker Compose is available"

  [ -f "$COMPOSE_FILE" ] || fail "Compose file not found: ${COMPOSE_FILE}"
  ok "Compose file found: ${COMPOSE_FILE}"

  SERVICES="$(docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null || true)"
  echo "$SERVICES" | grep -qx "$SERVICE" || fail "Service '${SERVICE}' not found in ${COMPOSE_FILE}"
  ok "Service '${SERVICE}' exists in compose config"

  if ! docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" sh -lc "echo container-ready >/dev/null" >/dev/null 2>&1; then
    fail "Cannot exec into service '${SERVICE}'. Is it running? Try: docker compose -f ${COMPOSE_FILE} up -d"
  fi
  ok "Service '${SERVICE}' is running and exec-capable"

  if ! docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" sh -lc "nvidia-smi >/dev/null 2>&1"; then
    fail "nvidia-smi not functional inside container (GPU passthrough/runtime issue)"
  fi
  ok "Container nvidia-smi is operational"

  log "Container GPU summary:"
  docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" sh -lc \
    "nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader 2>/dev/null || nvidia-smi" || true

  # PyTorch CUDA check inside container
  if ! docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" sh -lc \
    "python - <<'PY'
import json
import sys
try:
    import torch
except Exception as e:
    print(json.dumps({'ok': False, 'error': f'failed to import torch: {e}'}))
    sys.exit(2)

has_cuda = torch.cuda.is_available()
out = {
    'ok': bool(has_cuda),
    'torch_version': torch.__version__,
    'torch_cuda_version': getattr(torch.version, 'cuda', None),
    'cuda_available': bool(has_cuda),
    'cuda_device_count': int(torch.cuda.device_count()) if has_cuda else 0,
    'bf16_supported': bool(torch.cuda.is_bf16_supported()) if has_cuda else False,
}
if has_cuda and torch.cuda.device_count() > 0:
    out['cuda_device_0'] = torch.cuda.get_device_name(0)
    try:
        cc = torch.cuda.get_device_capability(0)
        out['compute_capability_0'] = f'{cc[0]}.{cc[1]}'
    except Exception:
        out['compute_capability_0'] = None

print(json.dumps(out))
if not has_cuda:
    sys.exit(3)
PY" >/tmp/check_gpu_torch.json 2>/tmp/check_gpu_torch.err; then
    cat /tmp/check_gpu_torch.err >&2 || true
    if [ -f /tmp/check_gpu_torch.json ]; then
      cat /tmp/check_gpu_torch.json >&2 || true
    fi
    fail "PyTorch CUDA check inside container failed"
  fi

  TORCH_JSON="$(cat /tmp/check_gpu_torch.json 2>/dev/null || true)"
  [ -n "$TORCH_JSON" ] || fail "Missing PyTorch check output from container"
  ok "PyTorch CUDA check passed inside container"
  printf '%s\n' "[INFO] Container torch summary: ${TORCH_JSON}"

  # Best-effort parse of compute capability from JSON (without jq)
  CC0="$(printf '%s\n' "$TORCH_JSON" | sed -n 's/.*"compute_capability_0":"\([^"]*\)".*/\1/p' || true)"
  if [ -n "$CC0" ]; then
    if version_ge "$CC0" "$MIN_CC"; then
      ok "Container device[0] compute capability ${CC0} >= ${MIN_CC}"
    else
      warn "Container device[0] compute capability ${CC0} < ${MIN_CC}"
    fi
  else
    warn "Could not parse compute capability from container torch output"
  fi
}

main() {
  parse_args "$@"

  log "GPU precondition script started"
  log "Mode=${MODE}, Compose=${COMPOSE_FILE}, Service=${SERVICE}, MinCC=${MIN_CC}"

  case "$MODE" in
    host)
      host_checks
      ;;
    container)
      container_checks
      ;;
    all)
      host_checks
      container_checks
      ;;
    *)
      fail "Invalid mode: ${MODE}"
      ;;
  esac

  log "Completed checks: pass=${PASS_COUNT}, warnings=${WARN_COUNT}"
  if [ "$WARN_COUNT" -gt 0 ]; then
    warn "Completed with warnings. Review output before long training runs."
  fi
  ok "GPU preconditions satisfied"
}

main "$@"
