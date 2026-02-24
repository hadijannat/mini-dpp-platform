#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SWARM_LOG_DIR:-$SCRIPT_DIR/logs}"

usage() {
  cat <<'EOF'
Usage: run-agent.sh --task-id <id> --agent <codex|claude> --model <model> --reasoning <level> --prompt-file <path> --attempt <n>
EOF
}

TASK_ID=""
AGENT=""
MODEL=""
REASONING="high"
PROMPT_FILE=""
ATTEMPT="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id)
      TASK_ID="$2"
      shift 2
      ;;
    --agent)
      AGENT="$2"
      shift 2
      ;;
    --model)
      MODEL="$2"
      shift 2
      ;;
    --reasoning)
      REASONING="$2"
      shift 2
      ;;
    --prompt-file)
      PROMPT_FILE="$2"
      shift 2
      ;;
    --attempt)
      ATTEMPT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$TASK_ID" || -z "$AGENT" || -z "$MODEL" || -z "$PROMPT_FILE" ]]; then
  usage
  exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/${TASK_ID}-${AGENT}-attempt${ATTEMPT}-${TIMESTAMP}.log"

log_line() {
  local line="$1"
  echo "$line" | tee -a "$LOG_FILE"
}

log_line "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting task=$TASK_ID agent=$AGENT model=$MODEL reasoning=$REASONING attempt=$ATTEMPT"
log_line "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Prompt file: $PROMPT_FILE"
log_line "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Working dir: $(pwd)"

PROMPT_CONTENT="$(cat "$PROMPT_FILE")"

set +e
case "$AGENT" in
  codex)
    CODEX_BIN="${SWARM_CODEX_BINARY:-codex}"
    CODEX_CMD=(
      "$CODEX_BIN"
      --model "$MODEL"
      -c "model_reasoning_effort=$REASONING"
      --dangerously-bypass-approvals-and-sandbox
      "$PROMPT_CONTENT"
    )
    if command -v script >/dev/null 2>&1; then
      if [[ "$(uname -s)" == "Darwin" ]]; then
        script -aq "$LOG_FILE" "${CODEX_CMD[@]}"
        STATUS=$?
      else
        COMMAND_STR="$(printf '%q ' "${CODEX_CMD[@]}")"
        script -aq "$LOG_FILE" -c "$COMMAND_STR"
        STATUS=$?
      fi
    else
      "${CODEX_CMD[@]}" 2>&1 | tee -a "$LOG_FILE"
      STATUS=${PIPESTATUS[0]}
    fi
    ;;
  claude)
    CLAUDE_BIN="${SWARM_CLAUDE_BINARY:-claude}"
    "$CLAUDE_BIN" \
      --model "$MODEL" \
      --dangerously-skip-permissions \
      -p "$PROMPT_CONTENT" 2>&1 | tee -a "$LOG_FILE"
    STATUS=${PIPESTATUS[0]}
    ;;
  *)
    log_line "Unsupported agent: $AGENT"
    STATUS=2
    ;;
esac
set -e

log_line "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Agent exit status: $STATUS"
exit "$STATUS"
