# OpenClaw-Style Swarm Playbook (Codex + Claude)

**As of:** 2026-02-24

This playbook adapts an OpenClaw-style orchestration workflow to this repository using only Codex and Claude agents.

## 1) Scope Boundary

Included:

- Codex coding agents
- Claude coding/review agents
- Local orchestration via `.clawdbot/`
- GitHub PR + CI + review gate checks via `gh`

Excluded:

- Gemini and other model reviewers
- Direct production DB access from coding agents

## 2) Orchestrator Responsibilities

Your orchestrator (human or OpenClaw) should:

- Convert customer/business context into precise coding prompts.
- Select `codex` vs `claude` per task.
- Spawn tasks with isolated worktrees and branches.
- Monitor deterministic signals, not token-heavy polling.
- Trigger retries/redirections when checks fail.

Coding agents should receive only code/task context needed for implementation.

## 3) Task Lifecycle in This Repo

### Step A: Prepare Prompt

Create prompt files under `.clawdbot/prompts/`.

Example:

```bash
cat > .clawdbot/prompts/feat-custom-templates.md <<'EOF'
Implement reusable template presets for team-level DPP configuration.
- Backend: add API support in backend/app/modules/templates/
- Frontend: expose template preset picker in frontend/src/features/
- Add/adjust tests.
- Open PR once complete.
EOF
```

### Step B: Spawn Agent

```bash
.clawdbot/spawn-agent.sh \
  --id feat-custom-templates \
  --agent codex \
  --description "Reusable team config templates" \
  --prompt-file "$PWD/.clawdbot/prompts/feat-custom-templates.md" \
  --notify-on-complete
```

Spawn behavior:

- Creates worktree (default root: sibling `mini-dpp-platform-worktrees/`).
- Creates branch (default: `feat/<task-id>`).
- Bootstraps deps unless `--skip-bootstrap`.
- Starts tmux session and writes logs.
- Registers task in `.clawdbot/active-tasks.json`.

### Step C: Monitor Loop

```bash
.clawdbot/check-agents.sh
```

Checks are deterministic and local:

- tmux session alive
- open PR on branch
- CI state (`gh pr checks`)
- Codex review approval
- Claude review approval
- screenshot evidence if UI changed

If blockers are found:

- live session: monitor sends corrective message to the agent
- dead session: monitor respawns agent (up to `maxAttempts`)

### Step D: Mid-Task Redirection

```bash
.clawdbot/redirect-agent.sh feat-custom-templates "Stop. Fix backend validation and CI failures first."
```

### Step E: Done Condition

Task auto-marks `done` only when all gates pass:

- PR created
- branch synced/no conflict
- CI passing
- Codex review approved
- Claude review approved
- screenshot proof for UI changes

## 4) Runtime Registry Contract

`.clawdbot/active-tasks.json` includes per-task state such as:

- task metadata (id, agent, branch, worktree, prompt)
- tmux session identity
- attempt/retry counters
- PR/check status snapshot
- completion timestamp and final note

## 5) Suggested Schedules

Monitor every 10 minutes:

```cron
*/10 * * * * cd /Users/aeroshariati/mini-dpp-platform && ./.clawdbot/check-agents.sh >> ./.clawdbot/logs/monitor.log 2>&1
```

Cleanup merged tasks daily:

```cron
15 22 * * * cd /Users/aeroshariati/mini-dpp-platform && ./.clawdbot/cleanup-worktrees.sh >> ./.clawdbot/logs/cleanup.log 2>&1
```

## 6) Model Routing Guidance (Codex + Claude only)

- Use Codex for backend logic, multi-file refactors, complex bugfixes.
- Use Claude for faster UI-focused implementation or repo plumbing tasks.
- Keep reviewer regexes configured so monitor can evaluate approvals:

```bash
export SWARM_CODEX_REVIEWER_REGEX=codex
export SWARM_CLAUDE_REVIEWER_REGEX=claude
```

## 7) Operational Rules

- One task per worktree/session.
- Keep prompt files versioned and auditable.
- Do not allow coding agents direct production-admin credentials.
- Fail fast on missing screenshot proof for UI PRs.
- Keep retries bounded; escalate to human review when retries are exhausted.
