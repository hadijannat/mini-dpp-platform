#!/usr/bin/env python3
"""Local Codex/Claude swarm orchestrator for mini-dpp-platform.

This script manages a task registry, per-task worktrees, tmux sessions,
and deterministic checks for PR/CI/review gates.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
REGISTRY_PATH = Path(os.getenv("SWARM_REGISTRY_PATH", SCRIPT_DIR / "active-tasks.json"))
WORKTREE_ROOT = Path(
    os.getenv("SWARM_WORKTREE_ROOT", str(REPO_ROOT.parent / f"{REPO_ROOT.name}-worktrees"))
)
DEFAULT_BASE_BRANCH = os.getenv("SWARM_BASE_BRANCH", "main")
DEFAULT_MAX_ATTEMPTS = int(os.getenv("SWARM_MAX_ATTEMPTS", "3"))
TERMINAL_STATES = {"done", "failed", "cancelled"}
FAIL_STATES = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
PENDING_STATES = {"PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "EXPECTED"}
PASS_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}

UI_FILE_PREFIXES = (
    "frontend/src/",
    "frontend/public/",
)
UI_FILE_SUFFIXES = (
    ".tsx",
    ".jsx",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".html",
    ".svg",
)


def now_ms() -> int:
    return int(time.time() * 1000)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def run_cmd(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        capture_output=capture,
        check=False,
    )
    if check and result.returncode != 0:
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        details = "\n".join(part for part in [stdout, stderr] if part)
        raise RuntimeError(f"command failed ({' '.join(args)}): {details}")
    return result


def run_shell(command: str, *, cwd: Path) -> None:
    result = subprocess.run(["bash", "-lc", command], cwd=str(cwd), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"shell command failed in {cwd}: {command}")


def require_tool(binary: str) -> None:
    if shutil.which(binary) is None:
        fail(f"required tool '{binary}' was not found in PATH")


def sanitize_task_id(raw: str) -> str:
    value = raw.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        fail("task id resolves to empty value after sanitization")
    return value


def default_branch(task_id: str) -> str:
    slug = task_id.replace("_", "-")
    return f"feat/{slug}"


def session_name(task_id: str) -> str:
    value = f"swarm-{task_id}"
    return value[:64]


def infer_default_model(agent: str) -> str:
    if agent == "codex":
        return os.getenv("SWARM_CODEX_MODEL_DEFAULT", "gpt-5.3-codex")
    return os.getenv("SWARM_CLAUDE_MODEL_DEFAULT", "claude-opus-4.5")


def default_bootstrap_command() -> str:
    return (
        "if [ -f backend/pyproject.toml ]; then "
        "(cd backend && uv sync --frozen --extra dev --extra test); "
        "fi; "
        "if [ -f frontend/package.json ]; then "
        "(cd frontend && npm ci); "
        "fi"
    )


def ensure_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"version": 1, "tasks": []}, indent=2) + "\n", encoding="utf-8")


@contextmanager
def locked_registry(path: Path):
    ensure_registry(path)
    with path.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        raw = handle.read().strip()
        if raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                fail(f"registry JSON parse error in {path}: {exc}")
        else:
            data = {"version": 1, "tasks": []}
        if not isinstance(data, dict):
            data = {"version": 1, "tasks": []}
        if not isinstance(data.get("tasks"), list):
            data["tasks"] = []

        yield data

        handle.seek(0)
        handle.truncate()
        json.dump(data, handle, indent=2, sort_keys=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def find_task(tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any] | None:
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None


def git_branch_exists(branch: str) -> bool:
    result = run_cmd(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


def create_worktree(*, worktree_path: Path, branch: str, base_branch: str) -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    if worktree_path.exists():
        if not (worktree_path / ".git").exists():
            fail(f"worktree path exists but is not a git worktree: {worktree_path}")
        return

    if git_branch_exists(branch):
        run_cmd(["git", "worktree", "add", str(worktree_path), branch], cwd=REPO_ROOT)
        return

    run_cmd(["git", "fetch", "origin", base_branch], cwd=REPO_ROOT)
    run_cmd(
        ["git", "worktree", "add", str(worktree_path), "-b", branch, f"origin/{base_branch}"],
        cwd=REPO_ROOT,
    )


def tmux_session_exists(name: str) -> bool:
    result = run_cmd(["tmux", "has-session", "-t", name], check=False)
    return result.returncode == 0


def build_agent_launch_command(
    *,
    task_id: str,
    agent: str,
    model: str,
    reasoning: str,
    prompt_file: Path,
    attempt: int,
) -> str:
    script = SCRIPT_DIR / "run-agent.sh"
    parts = [
        str(script),
        "--task-id",
        task_id,
        "--agent",
        agent,
        "--model",
        model,
        "--reasoning",
        reasoning,
        "--prompt-file",
        str(prompt_file),
        "--attempt",
        str(attempt),
    ]
    return " ".join(shlex.quote(part) for part in parts)


def start_tmux_task(task: dict[str, Any], *, prompt_file: Path, attempt: int) -> None:
    require_tool("tmux")
    if tmux_session_exists(task["tmuxSession"]):
        fail(f"tmux session already exists: {task['tmuxSession']}")

    command = build_agent_launch_command(
        task_id=task["id"],
        agent=task["agent"],
        model=task["model"],
        reasoning=task["reasoningEffort"],
        prompt_file=prompt_file,
        attempt=attempt,
    )

    run_cmd(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            task["tmuxSession"],
            "-c",
            task["worktreePath"],
            command,
        ],
        check=True,
        capture=False,
    )


def send_tmux_message(session: str, message: str) -> None:
    if not tmux_session_exists(session):
        raise RuntimeError(f"tmux session not running: {session}")
    run_cmd(["tmux", "send-keys", "-t", session, message, "Enter"], check=True)


def telegram_notify(message: str) -> None:
    token = os.getenv("SWARM_TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("SWARM_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 400:
                print(f"warning: telegram notify failed with status {response.status}", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"warning: telegram notify failed: {exc}", file=sys.stderr)


def get_open_pr_for_branch(branch: str) -> dict[str, Any] | None:
    if shutil.which("gh") is None:
        return None
    result = run_cmd(
        [
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--state",
            "open",
            "--json",
            "number,url,headRefName,baseRefName,isDraft",
        ],
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not data:
        return None
    return data[0]


def get_pr_details(pr_number: int) -> dict[str, Any]:
    result = run_cmd(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,url,body,mergeStateStatus,reviewDecision,isDraft,reviews,files,headRefName,baseRefName",
        ],
        check=False,
    )
    if result.returncode != 0:
        return {}
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {}


def get_pr_checks(pr_number: int) -> list[dict[str, Any]]:
    result = run_cmd(
        [
            "gh",
            "pr",
            "checks",
            str(pr_number),
            "--json",
            "name,state,link",
        ],
        check=False,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    return []


def evaluate_ci(checks: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if not checks:
        return "pending", []

    failures: list[str] = []
    pending: list[str] = []
    for check in checks:
        state = str(check.get("state") or "").upper()
        name = str(check.get("name") or "unknown-check")
        if state in FAIL_STATES:
            failures.append(name)
        elif state in PENDING_STATES or not state:
            pending.append(name)
        elif state in PASS_STATES:
            continue
        else:
            pending.append(name)

    if failures:
        return "fail", failures
    if pending:
        return "pending", pending
    return "pass", []


def compile_regex_from_env(var_name: str, default_pattern: str) -> re.Pattern[str]:
    value = os.getenv(var_name, default_pattern).strip()
    if not value:
        value = default_pattern
    return re.compile(value, re.IGNORECASE)


def latest_review_state_by_author(reviews: list[dict[str, Any]]) -> dict[str, str]:
    sortable = sorted(reviews, key=lambda review: str(review.get("submittedAt") or ""))
    latest: dict[str, str] = {}
    for review in sortable:
        author = review.get("author") or {}
        login = str(author.get("login") or "").strip().lower()
        if not login:
            continue
        latest[login] = str(review.get("state") or "").upper()
    return latest


def evaluate_model_review(reviews: list[dict[str, Any]], reviewer_regex: re.Pattern[str]) -> str:
    latest = latest_review_state_by_author(reviews)
    matched_states = [state for login, state in latest.items() if reviewer_regex.search(login)]
    if not matched_states:
        return "pending"
    if any(state == "CHANGES_REQUESTED" for state in matched_states):
        return "fail"
    if any(state == "APPROVED" for state in matched_states):
        return "pass"
    return "pending"


def is_ui_file(path: str) -> bool:
    path = path.strip()
    if path.startswith(UI_FILE_PREFIXES):
        return True
    if path.startswith("frontend/") and path.endswith(UI_FILE_SUFFIXES):
        return True
    return False


def has_screenshot_evidence(pr_body: str) -> bool:
    if re.search(r"!\[[^\]]*\]\([^)]+\)", pr_body or "", flags=re.MULTILINE):
        return True

    match = re.search(r"^- Screenshots \(if UI changes\):\s*(.+)$", pr_body or "", flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return False
    value = match.group(1).strip().lower()
    if value in {"", "-", "none", "n/a", "na", "not applicable"}:
        return False
    return True


def evaluate_ui_screenshot(pr_details: dict[str, Any]) -> tuple[str, bool]:
    files = pr_details.get("files") or []
    changed_ui = any(is_ui_file(str(file.get("path") or "")) for file in files)
    if not changed_ui:
        return "pass", False
    body = str(pr_details.get("body") or "")
    return ("pass" if has_screenshot_evidence(body) else "fail"), True


def branch_sync_state(pr_details: dict[str, Any]) -> str:
    merge_state = str(pr_details.get("mergeStateStatus") or "").upper()
    if not merge_state:
        return "pending"
    if merge_state in {"BEHIND", "DIRTY"}:
        return "fail"
    return "pass"


def write_retry_prompt(task: dict[str, Any], reason: str) -> Path:
    original_prompt = Path(task["promptFile"])
    if not original_prompt.exists():
        raise RuntimeError(f"prompt file no longer exists: {original_prompt}")

    next_attempt = int(task.get("attempts", 1)) + 1
    destination = SCRIPT_DIR / "runtime-prompts" / f"{task['id']}-attempt-{next_attempt}.md"
    source_text = original_prompt.read_text(encoding="utf-8")
    appendix = textwrap.dedent(
        f"""

        ---
        ## Retry Context (attempt {next_attempt})
        {reason}

        Focus on resolving only the blocking items and then re-run the required checks.
        """
    ).strip("\n")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source_text.rstrip() + "\n\n" + appendix + "\n", encoding="utf-8")
    return destination


def maybe_autorecover(task: dict[str, Any], reason: str, *, auto_respawn: bool) -> str:
    fingerprint = reason.strip()
    previous_fingerprint = str(task.get("lastFailureFingerprint") or "")
    session_alive = tmux_session_exists(task["tmuxSession"])

    if session_alive:
        if fingerprint and fingerprint != previous_fingerprint:
            send_tmux_message(
                task["tmuxSession"],
                f"Stop and address this blocker before continuing. {reason}",
            )
            task["lastFailureFingerprint"] = fingerprint
            task["lastDirectedAt"] = now_ms()
            return "redirected"
        return "waiting"

    if not auto_respawn:
        task["status"] = "failed"
        task["note"] = reason
        task["lastFailureFingerprint"] = fingerprint
        return "failed"

    attempts = int(task.get("attempts", 1))
    max_attempts = int(task.get("maxAttempts", DEFAULT_MAX_ATTEMPTS))
    if attempts >= max_attempts:
        task["status"] = "failed"
        task["note"] = f"{reason} (retries exhausted: {attempts}/{max_attempts})"
        task["lastFailureFingerprint"] = fingerprint
        return "exhausted"

    retry_prompt = write_retry_prompt(task, reason)
    task["activePromptFile"] = str(retry_prompt)
    task["attempts"] = attempts + 1
    start_tmux_task(task, prompt_file=retry_prompt, attempt=task["attempts"])
    task["status"] = "running"
    task["note"] = f"Respawned attempt {task['attempts']}"
    task["lastFailureFingerprint"] = fingerprint
    task["lastRespawnAt"] = now_ms()
    return "respawned"


def update_task_checks(task: dict[str, Any], *, auto_respawn: bool) -> str:
    task["lastCheckedAt"] = now_ms()
    pr = get_open_pr_for_branch(task["branch"])

    checks_payload: dict[str, Any] = {
        "prCreated": False,
        "branchSynced": False,
        "ciPassed": False,
        "codexReviewPassed": False,
        "claudeReviewPassed": False,
        "uiScreenshotProof": False,
    }

    status_detail: dict[str, Any] = {
        "ci": "pending",
        "codexReview": "pending",
        "claudeReview": "pending",
        "uiScreenshot": "pending",
        "branchSync": "pending",
        "draft": False,
    }

    if pr is None:
        task["checks"] = checks_payload
        task["checkDetails"] = status_detail
        if tmux_session_exists(task["tmuxSession"]):
            task["status"] = "running"
            task["note"] = "Agent session active; waiting for PR creation"
            return "running"

        result = maybe_autorecover(
            task,
            "tmux session ended before opening a PR.",
            auto_respawn=auto_respawn,
        )
        return result

    pr_number = int(pr["number"])
    task["pr"] = pr_number
    task["prUrl"] = pr.get("url")
    checks_payload["prCreated"] = True

    pr_details = get_pr_details(pr_number)
    pr_checks = get_pr_checks(pr_number)
    ci_state, ci_blockers = evaluate_ci(pr_checks)
    branch_state = branch_sync_state(pr_details)

    codex_regex = compile_regex_from_env("SWARM_CODEX_REVIEWER_REGEX", "codex")
    claude_regex = compile_regex_from_env("SWARM_CLAUDE_REVIEWER_REGEX", "claude")
    reviews = pr_details.get("reviews") or []

    codex_review_state = evaluate_model_review(reviews, codex_regex)
    claude_review_state = evaluate_model_review(reviews, claude_regex)
    ui_screenshot_state, ui_changed = evaluate_ui_screenshot(pr_details)

    checks_payload["branchSynced"] = branch_state == "pass"
    checks_payload["ciPassed"] = ci_state == "pass"
    checks_payload["codexReviewPassed"] = codex_review_state == "pass"
    checks_payload["claudeReviewPassed"] = claude_review_state == "pass"
    checks_payload["uiScreenshotProof"] = ui_screenshot_state == "pass"

    status_detail["ci"] = ci_state
    status_detail["codexReview"] = codex_review_state
    status_detail["claudeReview"] = claude_review_state
    status_detail["uiScreenshot"] = ui_screenshot_state
    status_detail["branchSync"] = branch_state
    status_detail["uiChanged"] = ui_changed
    status_detail["draft"] = bool(pr_details.get("isDraft"))

    task["checks"] = checks_payload
    task["checkDetails"] = status_detail

    done = (
        checks_payload["prCreated"]
        and checks_payload["branchSynced"]
        and checks_payload["ciPassed"]
        and checks_payload["codexReviewPassed"]
        and checks_payload["claudeReviewPassed"]
        and checks_payload["uiScreenshotProof"]
        and not status_detail["draft"]
    )

    if done:
        task["status"] = "done"
        task["completedAt"] = task.get("completedAt") or now_ms()
        task["note"] = "All gates passed. Ready to merge."
        if not task.get("notifiedDone") and task.get("notifyOnComplete", True):
            telegram_notify(
                f"✅ PR #{pr_number} is ready for review ({task['id']})\n"
                f"{task.get('description', '')}\n"
                f"{task.get('prUrl', '')}"
            )
            task["notifiedDone"] = True
        return "done"

    blockers: list[str] = []
    if status_detail["draft"]:
        blockers.append("PR is still draft")
    if branch_state == "fail":
        blockers.append("branch is behind main or has merge conflicts")
    if ci_state == "fail":
        blocker_names = ", ".join(ci_blockers) if ci_blockers else "CI checks failed"
        blockers.append(f"CI failing: {blocker_names}")
    if codex_review_state == "fail":
        blockers.append("Codex reviewer requested changes")
    if claude_review_state == "fail":
        blockers.append("Claude reviewer requested changes")
    if ui_screenshot_state == "fail":
        blockers.append("UI changes detected without screenshot evidence in PR body")

    if blockers:
        reason = "; ".join(blockers)
        recovery = maybe_autorecover(task, reason, auto_respawn=auto_respawn)
        if task.get("status") not in TERMINAL_STATES:
            task["status"] = "running"
            task["note"] = f"Blocking items detected ({recovery}): {reason}"
        return recovery

    task["status"] = "running"
    task["note"] = "Waiting for remaining gates"
    task["lastFailureFingerprint"] = ""
    return "running"


def cmd_init(_: argparse.Namespace) -> None:
    ensure_registry(REGISTRY_PATH)
    (SCRIPT_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (SCRIPT_DIR / "runtime-prompts").mkdir(parents=True, exist_ok=True)
    print(f"Initialized swarm registry at {REGISTRY_PATH}")


def cmd_spawn(args: argparse.Namespace) -> None:
    require_tool("git")
    require_tool("tmux")
    task_id = sanitize_task_id(args.id)
    agent = args.agent.lower()
    if agent not in {"codex", "claude"}:
        fail("agent must be one of: codex, claude")

    prompt_file = Path(args.prompt_file).expanduser().resolve()
    if not prompt_file.exists():
        fail(f"prompt file not found: {prompt_file}")

    branch = args.branch or default_branch(task_id)
    worktree_name = args.worktree_name or task_id
    worktree_root = Path(args.worktree_root).expanduser().resolve() if args.worktree_root else WORKTREE_ROOT
    worktree_path = (worktree_root / worktree_name).resolve()

    tmux_session = args.tmux_session or session_name(task_id)
    model = args.model or infer_default_model(agent)
    reasoning_effort = args.reasoning

    with locked_registry(REGISTRY_PATH) as registry:
        tasks = registry["tasks"]
        if find_task(tasks, task_id):
            fail(f"task already exists in registry: {task_id}")

        create_worktree(worktree_path=worktree_path, branch=branch, base_branch=args.base)

        if not args.skip_bootstrap:
            bootstrap = args.bootstrap or default_bootstrap_command()
            run_shell(bootstrap, cwd=worktree_path)

        task = {
            "id": task_id,
            "agent": agent,
            "description": args.description,
            "repo": REPO_ROOT.name,
            "repoPath": str(REPO_ROOT),
            "branch": branch,
            "baseBranch": args.base,
            "worktreeName": worktree_name,
            "worktreePath": str(worktree_path),
            "tmuxSession": tmux_session,
            "promptFile": str(prompt_file),
            "activePromptFile": str(prompt_file),
            "model": model,
            "reasoningEffort": reasoning_effort,
            "startedAt": now_ms(),
            "startedAtIso": now_iso(),
            "attempts": 1,
            "maxAttempts": args.max_attempts,
            "status": "running",
            "notifyOnComplete": bool(args.notify_on_complete),
            "checks": {
                "prCreated": False,
                "branchSynced": False,
                "ciPassed": False,
                "codexReviewPassed": False,
                "claudeReviewPassed": False,
                "uiScreenshotProof": False,
            },
            "checkDetails": {},
            "note": "Task spawned",
        }

        start_tmux_task(task, prompt_file=prompt_file, attempt=1)
        tasks.append(task)

    print(f"Spawned task '{task_id}'")
    print(f"- session: {tmux_session}")
    print(f"- branch: {branch}")
    print(f"- worktree: {worktree_path}")


def cmd_list(args: argparse.Namespace) -> None:
    ensure_registry(REGISTRY_PATH)
    with locked_registry(REGISTRY_PATH) as registry:
        tasks = registry["tasks"]

    if not tasks:
        print("No tasks in registry")
        return

    for task in tasks:
        if not args.all and task.get("status") in TERMINAL_STATES:
            continue
        pr = task.get("pr", "-")
        print(
            f"{task.get('id','?'):24} "
            f"agent={task.get('agent','?'):6} "
            f"status={task.get('status','?'):10} "
            f"attempts={task.get('attempts',0)}/{task.get('maxAttempts',0)} "
            f"pr={pr} "
            f"session={task.get('tmuxSession','?')}"
        )


def cmd_redirect(args: argparse.Namespace) -> None:
    task_id = sanitize_task_id(args.id)
    with locked_registry(REGISTRY_PATH) as registry:
        task = find_task(registry["tasks"], task_id)
        if not task:
            fail(f"task not found: {task_id}")
        send_tmux_message(task["tmuxSession"], args.message)
        task["lastDirectedAt"] = now_ms()
        task["note"] = "Manual redirection sent"
    print(f"Sent message to {task_id} ({task['tmuxSession']})")


def cmd_check(args: argparse.Namespace) -> None:
    require_tool("tmux")
    ensure_registry(REGISTRY_PATH)

    with locked_registry(REGISTRY_PATH) as registry:
        tasks = registry["tasks"]
        if not tasks:
            print("No active tasks")
            return

        summaries: list[str] = []
        for task in tasks:
            status = task.get("status")
            if status in TERMINAL_STATES and not args.include_terminal:
                continue
            outcome = update_task_checks(task, auto_respawn=args.auto_respawn)
            pr = task.get("pr", "-")
            summaries.append(
                f"{task['id']}: status={task.get('status')} outcome={outcome} pr={pr} note={task.get('note','')}"
            )

    if summaries:
        print("\n".join(summaries))
    else:
        print("No matching tasks to check")


def cmd_complete(args: argparse.Namespace) -> None:
    task_id = sanitize_task_id(args.id)
    with locked_registry(REGISTRY_PATH) as registry:
        task = find_task(registry["tasks"], task_id)
        if not task:
            fail(f"task not found: {task_id}")
        task["status"] = "done"
        task["completedAt"] = now_ms()
        task["note"] = args.note or "Marked done manually"
    print(f"Marked {task_id} as done")


def is_pr_merged(pr_number: int) -> bool:
    if shutil.which("gh") is None:
        return False
    result = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "state,mergedAt"],
        check=False,
    )
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return False
    merged_at = payload.get("mergedAt")
    return bool(merged_at)


def cmd_cleanup(args: argparse.Namespace) -> None:
    require_tool("git")
    ensure_registry(REGISTRY_PATH)

    removed = 0
    with locked_registry(REGISTRY_PATH) as registry:
        kept: list[dict[str, Any]] = []
        for task in registry["tasks"]:
            status = task.get("status")
            if status not in TERMINAL_STATES:
                kept.append(task)
                continue

            pr_number = task.get("pr")
            if args.merged_only and isinstance(pr_number, int) and not is_pr_merged(pr_number):
                kept.append(task)
                continue

            worktree_path = Path(task.get("worktreePath", ""))
            if args.remove_worktrees and worktree_path.exists():
                run_cmd(["git", "worktree", "remove", "--force", str(worktree_path)], cwd=REPO_ROOT, check=False)

            branch = task.get("branch")
            if args.remove_branches and isinstance(branch, str) and branch:
                run_cmd(["git", "branch", "-D", branch], cwd=REPO_ROOT, check=False)

            removed += 1

        registry["tasks"] = kept

    print(f"Cleanup complete. Removed {removed} task(s).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex/Claude local swarm manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize local swarm registry")
    init_parser.set_defaults(func=cmd_init)

    spawn = subparsers.add_parser("spawn", help="create worktree and start one agent session")
    spawn.add_argument("--id", required=True, help="stable task id")
    spawn.add_argument("--agent", required=True, choices=["codex", "claude"], help="agent type")
    spawn.add_argument("--description", required=True, help="short task description")
    spawn.add_argument("--prompt-file", required=True, help="path to prompt markdown/text")
    spawn.add_argument("--model", help="model name override")
    spawn.add_argument("--reasoning", default="high", help="model reasoning effort hint")
    spawn.add_argument("--branch", help="git branch name (default: feat/<id>)")
    spawn.add_argument("--base", default=DEFAULT_BASE_BRANCH, help="base branch (default: main)")
    spawn.add_argument("--worktree-name", help="folder name under worktree root")
    spawn.add_argument("--worktree-root", help="worktree root directory")
    spawn.add_argument("--tmux-session", help="tmux session name")
    spawn.add_argument("--bootstrap", help="shell command to bootstrap dependencies")
    spawn.add_argument("--skip-bootstrap", action="store_true", help="skip dependency bootstrap")
    spawn.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    spawn.add_argument(
        "--notify-on-complete",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="send Telegram notice when all gates pass (default: enabled)",
    )
    spawn.set_defaults(func=cmd_spawn)

    listing = subparsers.add_parser("list", help="list tracked tasks")
    listing.add_argument("--all", action="store_true", help="include done/failed tasks")
    listing.set_defaults(func=cmd_list)

    redirect = subparsers.add_parser("redirect", help="send corrective message to running task")
    redirect.add_argument("--id", required=True)
    redirect.add_argument("--message", required=True)
    redirect.set_defaults(func=cmd_redirect)

    check = subparsers.add_parser("check", help="evaluate task progress and gates")
    check.add_argument("--auto-respawn", action="store_true", help="respawn failed sessions when possible")
    check.add_argument("--include-terminal", action="store_true", help="also scan done/failed tasks")
    check.set_defaults(func=cmd_check)

    complete = subparsers.add_parser("complete", help="manually mark a task done")
    complete.add_argument("--id", required=True)
    complete.add_argument("--note", help="manual completion note")
    complete.set_defaults(func=cmd_complete)

    cleanup = subparsers.add_parser(
        "cleanup",
        help="remove terminal tasks from registry and optionally delete merged worktrees/branches",
    )
    cleanup.add_argument("--remove-worktrees", action="store_true")
    cleanup.add_argument("--remove-branches", action="store_true")
    cleanup.add_argument(
        "--merged-only",
        action="store_true",
        help="prune only tasks whose PR is merged (when PR exists)",
    )
    cleanup.set_defaults(func=cmd_cleanup)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except RuntimeError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
