#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 2 ]]; then
  cat <<'EOF'
Usage:
  .clawdbot/redirect-agent.sh <task-id> "message to running agent"
EOF
  exit 1
fi

TASK_ID="$1"
shift
MESSAGE="$*"

exec python3 "$SCRIPT_DIR/swarm.py" redirect --id "$TASK_ID" --message "$MESSAGE"
