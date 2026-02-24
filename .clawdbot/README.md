# Codex + Claude Swarm (Local)

This repository now includes a local swarm toolkit under `.clawdbot/`.

Scope is intentionally limited to:

- `codex` workers
- `claude` workers

No Gemini or other reviewer/agent integrations are included.

## What It Does

- Creates one git worktree per task.
- Runs each coding agent inside its own `tmux` session with persistent logs.
- Tracks task lifecycle in `.clawdbot/active-tasks.json`.
- Monitors progress with a deterministic loop:
  - tmux session alive check
  - PR existence for tracked branch
  - CI status (`gh pr checks`)
  - Codex + Claude review status
  - UI screenshot evidence gate
- Auto-recovers by:
  - redirecting a live session with corrective instructions
  - respawning a dead session (up to `maxAttempts`)
- Sends Telegram notifications when a task reaches "ready to merge" (optional).

## Files

- `.clawdbot/swarm.py`: orchestrator CLI.
- `.clawdbot/run-agent.sh`: executes Codex/Claude with logging.
- `.clawdbot/spawn-agent.sh`: convenience wrapper for `spawn`.
- `.clawdbot/check-agents.sh`: monitor loop wrapper (`check --auto-respawn`).
- `.clawdbot/redirect-agent.sh`: mid-task correction message.
- `.clawdbot/cleanup-worktrees.sh`: removes merged task worktrees/branches.
- `.clawdbot/active-tasks.json`: runtime registry (created automatically).

## Prerequisites

- `git`
- `tmux`
- `python3`
- `gh` (for PR/CI/review checks)
- `codex` CLI authenticated
- `claude` CLI authenticated

## One-Time Setup

```bash
python3 .clawdbot/swarm.py init
```

Optional environment variables:

```bash
# Agent binaries and model defaults
export SWARM_CODEX_BINARY=codex
export SWARM_CLAUDE_BINARY=claude
export SWARM_CODEX_MODEL_DEFAULT=gpt-5.3-codex
export SWARM_CLAUDE_MODEL_DEFAULT=claude-opus-4.5

# Reviewer detection (regex against PR review author login)
export SWARM_CODEX_REVIEWER_REGEX=codex
export SWARM_CLAUDE_REVIEWER_REGEX=claude

# Optional Telegram notifications
export SWARM_TELEGRAM_BOT_TOKEN=...
export SWARM_TELEGRAM_CHAT_ID=...

# Optional worktree root override
export SWARM_WORKTREE_ROOT="$HOME/worktrees/mini-dpp-platform"
```

## Spawn a Task

1. Write a prompt file, for example `.clawdbot/prompts/feat-custom-templates.md`.
2. Spawn the worker:

```bash
.clawdbot/spawn-agent.sh \
  --id feat-custom-templates \
  --agent codex \
  --description "Template reuse for team configurations" \
  --prompt-file "$PWD/.clawdbot/prompts/feat-custom-templates.md"
```

Useful spawn overrides:

- `--agent claude`
- `--model <override>`
- `--bootstrap "<shell command>"`
- `--skip-bootstrap`
- `--max-attempts 3`
- `--no-notify-on-complete`

## Monitor Loop

Manual check:

```bash
.clawdbot/check-agents.sh
```

Suggested cron (every 10 minutes):

```cron
*/10 * * * * cd /Users/aeroshariati/mini-dpp-platform && ./.clawdbot/check-agents.sh >> ./.clawdbot/logs/monitor.log 2>&1
```

List tasks:

```bash
python3 .clawdbot/swarm.py list --all
```

## Mid-Task Redirection

```bash
.clawdbot/redirect-agent.sh feat-custom-templates "Stop and fix API validation failures first. Ignore UI polish until CI is green."
```

## Done Criteria Enforced by Monitor

A task is marked `done` only when all are true:

- PR exists for the task branch.
- Branch is not behind and has no merge conflict (`mergeStateStatus`).
- CI checks are passing.
- Codex review is approved.
- Claude review is approved.
- If UI files changed, PR body includes screenshot evidence.

## Daily Cleanup

Remove finished merged task worktrees and branches:

```bash
.clawdbot/cleanup-worktrees.sh
```

Recommended daily cron:

```cron
15 22 * * * cd /Users/aeroshariati/mini-dpp-platform && ./.clawdbot/cleanup-worktrees.sh >> ./.clawdbot/logs/cleanup.log 2>&1
```
