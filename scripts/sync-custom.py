#!/usr/bin/env python3
"""Safely integrate upstream and feature branches into a fork's custom branch."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import NoReturn, TextIO


OWNER_MARKER = "shelley-sync-custom-state-v1\n"
BOT_NAME = "Shelley integration bot"
BOT_EMAIL = "shelley-integration-bot@localhost"


class SyncError(RuntimeError):
    pass


class InputError(SyncError):
    def __init__(self, message: str, snapshot: dict[str, object]):
        super().__init__(message)
        self.snapshot = snapshot


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise SyncError(f"command failed ({result.returncode}): {' '.join(args)}\n{detail}")
    return result


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo, check=check)


def atomic_json(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def read_attempt(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SyncError(f"invalid attempt record: {path}")
    return value


def write_attempt(
    path: Path,
    status: str,
    snapshot: dict[str, object],
    message: str,
    **details: object,
) -> None:
    record: dict[str, object] = {
        "status": status,
        "timestamp": now(),
        "input": snapshot,
        "message": message,
    }
    record.update(details)
    atomic_json(path, record)


def fail_attempt(
    path: Path,
    snapshot: dict[str, object],
    message: str,
    **details: object,
) -> NoReturn:
    write_attempt(path, "failed", snapshot, message, **details)
    raise SyncError(message)


def claim_state(state: Path) -> None:
    marker = state / ".sync-custom-owned"
    if marker.exists():
        if marker.is_symlink() or marker.read_text() != OWNER_MARKER:
            raise SyncError(f"state ownership marker is invalid: {marker}")
        return
    occupants = [entry.name for entry in state.iterdir() if entry.name != "lock"]
    if occupants:
        raise SyncError(
            f"refusing to claim non-empty unowned state directory {state}: "
            + ", ".join(sorted(occupants))
        )
    try:
        with marker.open("x") as output:
            output.write(OWNER_MARKER)
    except FileExistsError:
        if marker.is_symlink() or marker.read_text() != OWNER_MARKER:
            raise SyncError(f"state ownership marker is invalid: {marker}")


def initialize_repo(state: Path, upstream: str, fork: str) -> Path:
    repo = state / "workspace"
    if repo.is_symlink():
        raise SyncError(f"workspace must not be a symlink: {repo}")
    if not repo.exists():
        temporary = state / f"workspace.init-{os.getpid()}"
        if temporary.exists():
            raise SyncError(f"temporary initialization path already exists: {temporary}")
        try:
            run(
                [
                    "git",
                    "clone",
                    "--origin",
                    "origin",
                    "--no-local",
                    "--tags",
                    upstream,
                    str(temporary),
                ]
            )
            git(temporary, "remote", "add", "fork", fork)
            configure_repo(temporary)
            os.rename(temporary, repo)
        except Exception:
            if temporary.exists() and temporary.parent == state:
                shutil.rmtree(temporary)
            raise
    if not repo.is_dir() or not (repo / ".git").is_dir():
        raise SyncError(f"owned workspace is not a Git checkout: {repo}")
    verify_remote(repo, "origin", upstream)
    verify_remote(repo, "fork", fork)
    configure_repo(repo)
    return repo.resolve()


def verify_remote(repo: Path, name: str, expected: str) -> None:
    result = git(repo, "remote", "get-url", name, check=False)
    actual = result.stdout.strip() if result.returncode == 0 else None
    if actual != expected:
        raise SyncError(f"workspace remote {name!r} is {actual!r}, expected {expected!r}")


def configure_repo(repo: Path) -> None:
    git(repo, "config", "--local", "user.name", BOT_NAME)
    git(repo, "config", "--local", "user.email", BOT_EMAIL)
    git(repo, "config", "--local", "commit.gpgSign", "false")


def ensure_clean(repo: Path) -> None:
    status = git(repo, "status", "--porcelain=v1", "--untracked-files=no").stdout
    if status:
        raise SyncError(
            f"refusing to discard tracked changes in owned workspace {repo}:\n{status.rstrip()}"
        )
    for pseudoref in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        if git(repo, "rev-parse", "-q", "--verify", pseudoref, check=False).returncode == 0:
            raise SyncError(f"refusing workspace with operation in progress: {pseudoref}")


def fetch(repo: Path) -> None:
    git(
        repo,
        "fetch",
        "--prune",
        "origin",
        "+refs/heads/*:refs/remotes/origin/*",
        "+refs/tags/*:refs/tags/*",
    )
    git(
        repo,
        "fetch",
        "--prune",
        "fork",
        "+refs/heads/*:refs/remotes/fork/*",
    )


def resolve(repo: Path, ref: str) -> str | None:
    result = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def parse_manifest(repo: Path, text: str) -> list[str]:
    branches: list[str] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        branch = raw_line.partition("#")[0].strip()
        if not branch:
            continue
        if any(character.isspace() for character in branch):
            raise SyncError(f"invalid feature branch on line {line_number}: {branch!r}")
        if branch in {"main", "custom", "HEAD"}:
            raise SyncError(f"reserved branch in feature manifest: {branch}")
        if branch.startswith(("-", "refs/", "remotes/")):
            raise SyncError(f"invalid feature branch on line {line_number}: {branch!r}")
        valid = git(repo, "check-ref-format", f"refs/heads/{branch}", check=False)
        if valid.returncode:
            raise SyncError(f"invalid feature branch on line {line_number}: {branch!r}")
        if branch in seen:
            raise SyncError(f"duplicate feature branch in manifest: {branch}")
        seen.add(branch)
        branches.append(branch)
    return branches


def collect_snapshot(repo: Path) -> dict[str, object]:
    upstream_main = resolve(repo, "refs/remotes/origin/main")
    fork_main = resolve(repo, "refs/remotes/fork/main")
    fork_custom = resolve(repo, "refs/remotes/fork/custom")
    manifest: str | None = None
    manifest_error: str | None = None
    branches: list[str] = []

    if fork_custom:
        shown = git(
            repo,
            "show",
            f"{fork_custom}:.shelley-features",
            check=False,
        )
        if shown.returncode:
            manifest_error = "fork/custom does not contain .shelley-features"
        else:
            manifest = shown.stdout
            try:
                branches = parse_manifest(repo, manifest)
            except SyncError as error:
                manifest_error = str(error)

    features = [
        {"branch": branch, "sha": resolve(repo, f"refs/remotes/fork/{branch}")}
        for branch in branches
    ]
    snapshot: dict[str, object] = {
        "upstream_main": upstream_main,
        "fork_main": fork_main,
        "fork_custom": fork_custom,
        "feature_config": manifest,
        "feature_config_sha256": (
            hashlib.sha256(manifest.encode()).hexdigest() if manifest is not None else None
        ),
        "features": features,
    }

    problems: list[str] = []
    if not upstream_main:
        problems.append("missing upstream main branch")
    if not fork_main:
        problems.append("missing fork main branch")
    if not fork_custom:
        problems.append("missing fork custom branch")
    if manifest_error:
        problems.append(manifest_error)
    missing = [str(item["branch"]) for item in features if item["sha"] is None]
    if missing:
        problems.append("missing configured fork feature branches: " + ", ".join(missing))
    if problems:
        raise InputError("; ".join(problems), snapshot)
    return snapshot


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = git(repo, "merge-base", "--is-ancestor", ancestor, descendant, check=False)
    if result.returncode not in (0, 1):
        detail = (result.stderr or result.stdout).strip()
        raise SyncError(f"cannot compare commits {ancestor} and {descendant}: {detail}")
    return result.returncode == 0


def restore_after_merge_failure(repo: Path, starting_sha: str) -> str | None:
    errors: list[str] = []
    if git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0:
        aborted = git(repo, "merge", "--abort", check=False)
        if aborted.returncode:
            errors.append((aborted.stderr or aborted.stdout).strip())
    checked_out = git(repo, "checkout", "--detach", starting_sha, check=False)
    if checked_out.returncode:
        errors.append((checked_out.stderr or checked_out.stdout).strip())
    return "; ".join(filter(None, errors)) or None


def merge_candidate(
    repo: Path,
    snapshot: dict[str, object],
    attempt_path: Path,
) -> str:
    starting_sha = str(snapshot["fork_custom"])
    git(repo, "checkout", "--detach", starting_sha)
    targets = [("upstream/main", str(snapshot["upstream_main"]))]
    targets.extend(
        (f"fork/{item['branch']}", str(item["sha"]))
        for item in snapshot["features"]  # type: ignore[union-attr]
    )
    for label, sha in targets:
        merged = git(repo, "merge", "--no-ff", "--no-edit", sha, check=False)
        if merged.returncode:
            output = "\n".join(part.strip() for part in (merged.stdout, merged.stderr) if part.strip())
            recovery_error = restore_after_merge_failure(repo, starting_sha)
            fail_attempt(
                attempt_path,
                snapshot,
                f"merge failed for {label}",
                command_output=output,
                recovery_error=recovery_error,
            )
    candidate = resolve(repo, "HEAD")
    if not candidate:
        fail_attempt(attempt_path, snapshot, "candidate HEAD is not a commit")
    return candidate


def validation_event(log: TextIO, message: str, *, leading_newline: bool = False) -> None:
    prefix = "\n" if leading_newline else ""
    line = f"{prefix}[{now()}] {message}\n"
    log.write(line)
    log.flush()
    print(line, end="", flush=True)


def run_validator(
    repo: Path,
    executable: str,
    snapshot: dict[str, object],
    attempt_path: Path,
    validation_log: Path,
) -> dict[str, object]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(validation_log, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", errors="replace") as output:
        validation_event(output, f"validation started: {executable} {repo}")
        try:
            process = subprocess.Popen(
                [executable, str(repo)],
                cwd=repo,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
            )
        except OSError as error:
            validation_event(output, f"validation launch failed: {error}")
            fail_attempt(
                attempt_path,
                snapshot,
                "validator could not be started",
                validator_exit_code=127,
                validation_log=str(validation_log),
            )
        assert process.stdout is not None
        last_had_newline = True
        for chunk in process.stdout:
            output.write(chunk)
            output.flush()
            print(chunk, end="", flush=True)
            last_had_newline = chunk.endswith("\n")
        exit_code = process.wait()
        validation_event(
            output,
            f"validation finished with exit code {exit_code}",
            leading_newline=not last_had_newline,
        )

    validator_details: dict[str, object] = {
        "validator_exit_code": exit_code,
        "validation_log": str(validation_log),
    }
    if exit_code:
        fail_attempt(attempt_path, snapshot, "validator failed", **validator_details)
    status = git(repo, "status", "--porcelain=v1", "--untracked-files=no").stdout
    if status:
        fail_attempt(
            attempt_path,
            snapshot,
            "validator modified tracked files; changes preserved for inspection",
            tracked_changes=status,
            **validator_details,
        )
    return validator_details


def unchanged_failed(attempt: dict[str, object] | None, snapshot: dict[str, object]) -> bool:
    return bool(attempt and attempt.get("status") == "failed" and attempt.get("input") == snapshot)


def refresh_and_compare(
    repo: Path,
    original: dict[str, object],
    attempt_path: Path,
    failure_details: dict[str, object] | None = None,
) -> None:
    details = failure_details or {}
    fetch(repo)
    try:
        current = collect_snapshot(repo)
    except InputError as error:
        fail_attempt(
            attempt_path,
            original,
            "remote inputs changed while candidate was being prepared",
            refreshed_input=error.snapshot,
            refreshed_error=str(error),
            **details,
        )
    if current != original:
        fail_attempt(
            attempt_path,
            original,
            "remote inputs changed while candidate was being prepared",
            refreshed_input=current,
            **details,
        )


def push(repo: Path, snapshot: dict[str, object], candidate: str) -> None:
    upstream_main = str(snapshot["upstream_main"])
    git(
        repo,
        "push",
        "--atomic",
        "fork",
        f"{upstream_main}:refs/heads/main",
        f"{candidate}:refs/heads/custom",
    )


def synchronize(args: argparse.Namespace) -> int:
    state = Path(args.state).expanduser().resolve()
    if state.exists() and not state.is_dir():
        raise SyncError(f"state path is not a directory: {state}")
    state.mkdir(parents=True, exist_ok=True)
    lock_path = state / "lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("another sync-custom run holds the state lock; exiting")
            return 0

        claim_state(state)
        repo = initialize_repo(state, args.upstream, args.fork)
        ensure_clean(repo)
        fetch(repo)
        attempt_path = state / "attempt.json"
        previous = read_attempt(attempt_path)
        try:
            snapshot = collect_snapshot(repo)
        except InputError as error:
            if unchanged_failed(previous, error.snapshot) and not args.retry:
                raise SyncError(
                    "inputs match the previous failed attempt; refusing to retry unchanged "
                    "candidate without --retry"
                )
            fail_attempt(attempt_path, error.snapshot, str(error))

        if unchanged_failed(previous, snapshot) and not args.retry:
            raise SyncError(
                "inputs match the previous failed attempt; refusing to retry unchanged "
                "candidate without --retry"
            )

        upstream_main = str(snapshot["upstream_main"])
        fork_main = str(snapshot["fork_main"])
        fork_custom = str(snapshot["fork_custom"])
        if not is_ancestor(repo, fork_main, upstream_main):
            fail_attempt(
                attempt_path,
                snapshot,
                "fork/main is not an ancestor of upstream/main; refusing to overwrite divergent main",
            )

        required = [upstream_main]
        required.extend(str(item["sha"]) for item in snapshot["features"])  # type: ignore[union-attr]
        custom_current = all(is_ancestor(repo, sha, fork_custom) for sha in required)

        if custom_current:
            if fork_main == upstream_main:
                write_attempt(
                    attempt_path,
                    "success",
                    snapshot,
                    "already synchronized",
                    candidate=fork_custom,
                    published=False,
                )
                print("already synchronized")
                return 0
            refresh_and_compare(repo, snapshot, attempt_path)
            push(repo, snapshot, fork_custom)
            write_attempt(
                attempt_path,
                "success",
                snapshot,
                "synchronized fork/main; fork/custom was already current",
                candidate=fork_custom,
                published=True,
            )
            print("synchronized fork/main; fork/custom was already current")
            return 0

        candidate = merge_candidate(repo, snapshot, attempt_path)
        validation = run_validator(
            repo,
            args.validate,
            snapshot,
            attempt_path,
            state / "validation.log",
        )
        refresh_and_compare(repo, snapshot, attempt_path, validation)
        try:
            push(repo, snapshot, candidate)
        except SyncError as error:
            fail_attempt(
                attempt_path,
                snapshot,
                "atomic push failed; remote refs were not overwritten",
                candidate=candidate,
                push_error=str(error),
                **validation,
            )
        write_attempt(
            attempt_path,
            "success",
            snapshot,
            "published synchronized main and custom branches",
            candidate=candidate,
            published=True,
            **validation,
        )
        print(f"published candidate {candidate}")
        return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--upstream", required=True, help="official upstream Git URL")
    result.add_argument("--fork", required=True, help="user fork Git URL")
    result.add_argument("--state", required=True, help="persistent owned state directory")
    result.add_argument("--validate", required=True, help="validator executable")
    result.add_argument(
        "--retry",
        action="store_true",
        help="retry even when the input snapshot matches the previous failed attempt",
    )
    return result


def main() -> int:
    try:
        return synchronize(parser().parse_args())
    except SyncError as error:
        print(f"sync-custom: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
