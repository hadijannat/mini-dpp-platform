#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -eq 0 ]]; then
  cat <<'EOF'
Usage:
  .clawdbot/spawn-agent.sh \
    --id <task-id> \
    --agent <codex|claude> \
    --description "..." \
    --prompt-file /abs/path/to/prompt.md \
    [--notify-on-complete]

Example:
  .clawdbot/spawn-agent.sh --id feat-custom-templates --agent codex \
    --description "Custom templates feature" \
    --prompt-file "$PWD/.clawdbot/prompts/feat-custom-templates.md" \
    --notify-on-complete
EOF
  exit 0
fi

exec python3 "$SCRIPT_DIR/swarm.py" spawn "$@"
