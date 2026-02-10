# Claude Code Agent Teams: Technical Reference for `mini-dpp-platform`

**As of:** 2026-02-09

This document standardizes how this repository uses Claude Code multi-agent features for complex engineering work.

## 1) Two Systems You Must Distinguish

Claude Code provides two different multi-agent mechanisms:

| Capability | Task Subagents | Agent Teams |
|---|---|---|
| Lifetime | Short-lived worker inside one session | Independent teammate sessions |
| Communication | Reports only to caller | Direct peer-to-peer messaging |
| Coordination | Lead manually coordinates | Shared task queue + dependencies |
| Nesting | Cannot spawn subagents | Cannot create sub-teams |
| Typical use | Focused exploration/implementation | Large multi-phase workflows |
| Relative cost | Lower | Higher (separate context windows) |

Use **Task subagents** for focused work; use **Agent Teams** for coordinated, dependency-driven projects.

## 2) Enabling Agent Teams

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

Team data locations (local environment):

- `~/.claude/teams/{team-name}/`
- `~/.claude/tasks/{team-name}/`

## 3) Task Tool Syntax (Subagents)

```xml
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="description">Short task description</parameter>
  <parameter name="prompt">Detailed instructions with all required context</parameter>
  <parameter name="run_in_background">true</parameter>
  <parameter name="model">sonnet</parameter>
</invoke>
```

Common parameters:

- `subagent_type` (required)
- `description` (required)
- `prompt` (required)
- `run_in_background` (optional)
- `model` (optional)
- `resume` (optional)

## 4) Agent Teams Syntax (Team + Teammates + Tasks)

### Spawn team and teammates

```javascript
Teammate({ operation: "spawnTeam", team_name: "aas-dpp-enhance" })

Task({
  team_name: "aas-dpp-enhance",
  name: "parser-review",
  subagent_type: "general-purpose",
  prompt: "Inspect parser/schema fidelity and report to team-lead.",
  run_in_background: true
})
```

### Create task dependencies

```javascript
TaskCreate({ subject: "Research current state" })      // #1
TaskCreate({ subject: "Create implementation plan" })  // #2
TaskCreate({ subject: "Implement changes" })           // #3

TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
```

## 5) Teammate Operations Used by This Repo

Use these operations when coordinating teams:

- `spawnTeam`
- `discoverTeams`
- `requestJoin`
- `approveJoin`
- `rejectJoin`
- `write`
- `broadcast`
- `requestShutdown`
- `approveShutdown`
- `rejectShutdown`
- `approvePlan`
- `rejectPlan`
- `cleanup`

## 6) Orchestration Patterns

1. **Hub-and-Spoke**: lead + parallel specialists.
2. **Pipeline**: strict dependency ordering via `addBlockedBy`.
3. **Swarm**: many workers claim many independent tasks.
4. **Competing Proposals**: multiple teammates investigate same issue independently.
5. **Worker-Watcher**: teammate plans require lead approval before coding.
6. **Research + Implementation**: research first, then implementation with explicit handoff context.

## 7) Constraints and Anti-Patterns

### Hard constraints

- Subagents cannot spawn their own subagents.
- Agent teams cannot create nested teams.
- Teammates do not inherit lead chat context; pass context explicitly.
- One team per session.

### Anti-patterns to avoid

- Multiple teammates editing the same file without explicit ownership.
- Vague prompts without path boundaries and acceptance criteria.
- Using full team orchestration for simple linear tasks.
- Running long unattended loops without progress checks.

## 8) Token and Context Economics

- Each teammate has its own context window.
- Team workflows multiply token usage relative to a single session.
- Preferred cost pattern for complex runs: stronger lead model + lighter worker models.
- Keep instructions concise and avoid oversized always-loaded context files.

## 9) Repository-Specific AAS/DPP Adaptation

Primary pipeline under inspection:

1. IDTA submodel template resolution/fetch (`backend/app/modules/templates/`)
2. Parser + definition + schema generation (`backend/app/modules/templates/`)
3. Dynamic editor rendering (`frontend/src/features/editor/`)
4. DPP revision persistence (`backend/app/modules/dpps/`, `backend/app/db/`)
5. Export and conformance (`backend/app/modules/export/`, `backend/app/modules/aas/`)
6. Public viewer access (`backend/app/modules/dpps/public_router.py`, `frontend/src/features/viewer/`)

Useful local commands:

```bash
# Backend checks
cd backend
uv run pytest tests/unit/test_template_service.py tests/unit/test_export_service.py -q
uv run ruff check app/modules/templates app/modules/dpps app/modules/export

# Frontend checks
cd frontend
npm run test -- --run src/features/editor/components/AASRenderer.test.tsx
npm run typecheck
```

## 10) Recommended Team Lead Operating Contract

- Assign strict file ownership per teammate.
- Require reproducible evidence for every finding (test/log/code reference).
- Gate implementation on approved plans for high-risk changes.
- Keep a single findings register and alignment matrix as source of truth.
- Merge only after dependency chain is complete and regression checks pass.

## 11) References

- [mini-dpp-platform README](../../README.md)
- [Inspection Squad Playbook](./aas-dpp-inspection-squad-playbook.md)
- [IDTA DPP4.0 overview](https://industrialdigitaltwin.org/dpp4-0)
- [IDTA submodel templates repository](https://github.com/admin-shell-io/submodel-templates)
- [Eclipse BaSyx Python SDK](https://github.com/eclipse-basyx/basyx-python-sdk)
