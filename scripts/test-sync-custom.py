#!/usr/bin/env python3
"""Offline integration tests for sync-custom.py."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("sync-custom.py").resolve()


def command(
    *args: str | Path,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(map(str, args))}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def write(path: Path, contents: str) -> None:
    path.write_text(contents)


class SyncCustomTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.dev = self.root / "canonical"
        self.upstream = self.root / "upstream.git"
        self.fork = self.root / "fork.git"
        self.state = self.root / "state"
        self.validator = self.make_validator("exit 0\n")
        self.make_repositories(["feature/one"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return command("git", *args, cwd=cwd or self.dev)

    def make_validator(self, body: str) -> Path:
        path = self.root / f"validator-{len(list(self.root.glob('validator-*')))}"
        write(path, "#!/bin/sh\nset -eu\n" + body)
        path.chmod(0o755)
        return path

    def commit(self, message: str, *paths: str) -> str:
        self.git("add", *paths)
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def make_repositories(self, features: list[str]) -> None:
        self.git("init", "-b", "main", str(self.dev), cwd=self.root)
        self.git("config", "user.name", "Test Author")
        self.git("config", "user.email", "test@example.invalid")
        write(self.dev / "base.txt", "base\n")
        write(self.dev / "conflict.txt", "common\n")
        self.commit("base", "base.txt", "conflict.txt")

        self.git("init", "--bare", str(self.upstream), cwd=self.root)
        self.git("remote", "add", "upstream", str(self.upstream))
        self.git("push", "upstream", "main")

        self.git("init", "--bare", str(self.fork), cwd=self.root)
        self.git("remote", "add", "fork", str(self.fork))
        self.git("push", "fork", "main")

        self.git("checkout", "-b", "custom", "main")
        write(self.dev / ".shelley-features", "\n".join(features) + "\n")
        write(self.dev / "maintenance.txt", "fork maintenance\n")
        self.commit("custom maintenance", ".shelley-features", "maintenance.txt")
        self.git("push", "fork", "custom")

        for index, feature in enumerate(features, 1):
            self.git("checkout", "-b", feature, "main")
            filename = f"feature-{index}.txt"
            write(self.dev / filename, f"{feature}\n")
            self.commit(f"add {feature}", filename)
            self.git("push", "fork", feature)
        self.git("checkout", "custom")

    def sync(
        self,
        *,
        validator: Path | None = None,
        retry: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        args = [
            sys.executable,
            SCRIPT,
            "--upstream",
            self.upstream,
            "--fork",
            self.fork,
            "--state",
            self.state,
            "--validate",
            validator or self.validator,
        ]
        if retry:
            args.append("--retry")
        return command(*args, cwd=self.root, check=False)

    def remote_sha(self, remote: Path, branch: str) -> str:
        return command("git", "--git-dir", remote, "rev-parse", f"refs/heads/{branch}").stdout.strip()

    def remote_file(self, branch: str, filename: str) -> str:
        return command(
            "git", "--git-dir", self.fork, "show", f"refs/heads/{branch}:{filename}"
        ).stdout

    def assert_ancestor(self, ancestor: str, descendant: str) -> None:
        result = command(
            "git",
            "--git-dir",
            self.fork,
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def update_custom_manifest(self, contents: str) -> str:
        self.git("checkout", "custom")
        write(self.dev / ".shelley-features", contents)
        sha = self.commit("update feature manifest", ".shelley-features")
        self.git("push", "fork", "custom")
        return sha

    def test_success_noop_feature_advance_and_canonical_untouched(self) -> None:
        # Add a second independent feature before the first integration.
        self.git("checkout", "-b", "feature/two", "main")
        write(self.dev / "feature-2.txt", "feature/two\n")
        feature_two = self.commit("add feature/two", "feature-2.txt")
        self.git("push", "fork", "feature/two")
        self.git("checkout", "custom")
        write(self.dev / ".shelley-features", "# enabled branches\nfeature/one\nfeature/two # UI\n")
        self.commit("enable second feature", ".shelley-features")
        self.git("push", "fork", "custom")

        counter = self.root / "validator-count"
        validator = self.make_validator(
            f"printf '%s\\n' \"$1\" >> {shlex.quote(str(counter))}\n"
        )
        canonical_head = self.git("rev-parse", "HEAD").stdout.strip()
        canonical_status = self.git("status", "--porcelain=v1").stdout

        first = self.sync(validator=validator)
        self.assertEqual(first.returncode, 0, first.stderr)
        custom = self.remote_sha(self.fork, "custom")
        first_attempt = json.loads((self.state / "attempt.json").read_text())
        validation_log = self.state / "validation.log"
        self.assertEqual(first_attempt["candidate"], custom)
        self.assertEqual(first_attempt["validation_log"], str(validation_log))
        self.assertEqual(first_attempt["validator_exit_code"], 0)
        self.assertIn("validation started", validation_log.read_text())
        self.assertIn("validation finished with exit code 0", validation_log.read_text())
        self.assertIn("validation started", first.stdout)
        self.assert_ancestor(self.remote_sha(self.fork, "feature/one"), custom)
        self.assert_ancestor(feature_two, custom)
        self.assertEqual(self.remote_file("custom", "maintenance.txt"), "fork maintenance\n")
        self.assertEqual(counter.read_text().splitlines(), [str((self.state / "workspace").resolve())])

        second = self.sync(validator=validator)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already synchronized", second.stdout)
        self.assertEqual(len(counter.read_text().splitlines()), 1)

        self.git("checkout", "feature/one")
        write(self.dev / "feature-later.txt", "later\n")
        advanced = self.commit("advance feature one", "feature-later.txt")
        self.git("push", "fork", "feature/one")
        self.git("checkout", "custom")
        third = self.sync(validator=validator)
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assert_ancestor(advanced, self.remote_sha(self.fork, "custom"))
        self.assertEqual(len(counter.read_text().splitlines()), 2)

        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), canonical_head)
        self.assertEqual(self.git("status", "--porcelain=v1").stdout, canonical_status)

    def test_merge_identity_uses_owner_email_even_with_inherited_overrides(self) -> None:
        before = self.remote_sha(self.fork, "custom")
        validator = self.make_validator(
            'test "$GIT_AUTHOR_EMAIL" = inherited@example.invalid\n'
        )
        with patch.dict(os.environ, {
            "GIT_AUTHOR_NAME": "Inherited Author",
            "GIT_AUTHOR_EMAIL": "inherited@example.invalid",
            "GIT_COMMITTER_NAME": "Inherited Committer",
            "GIT_COMMITTER_EMAIL": "committer@example.invalid",
        }):
            result = self.sync(validator=validator)
        self.assertEqual(result.returncode, 0, result.stderr)
        identities = command(
            "git", "--git-dir", self.fork, "log", "--first-parent",
            "--format=%an <%ae>|%cn <%ce>", f"{before}..custom",
        ).stdout.splitlines()
        self.assertEqual(identities, [
            "Swaroop CH <swaroop@swaroopch.com>|Swaroop CH <swaroop@swaroopch.com>"
        ])
        subjects = command(
            "git", "--git-dir", self.fork, "log", "--first-parent",
            "--format=%s", f"{before}..custom",
        ).stdout.splitlines()
        self.assertEqual(subjects, ["chore(sync): merge fork/feature/one"])
        # Existing/upstream contributors are not relabeled by integration.
        author = command(
            "git", "--git-dir", self.fork, "show", "-s", "--format=%ae", "main",
        ).stdout.strip()
        self.assertEqual(author, "test@example.invalid")
        self.assertEqual(
            self.git("config", "user.email", cwd=self.state / "workspace").stdout.strip(),
            "swaroop@swaroopch.com",
        )

    def test_missing_feature_is_suppressed_until_inputs_change(self) -> None:
        before = self.update_custom_manifest("feature/missing\n")
        first = self.sync()
        self.assertNotEqual(first.returncode, 0)
        self.assertIn("missing configured fork feature branches", first.stderr)
        self.assertEqual(self.remote_sha(self.fork, "custom"), before)

        second = self.sync()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("previous failed attempt", second.stderr)

        self.git("checkout", "-b", "feature/missing", "main")
        write(self.dev / "missing.txt", "now present\n")
        feature = self.commit("create missing feature", "missing.txt")
        self.git("push", "fork", "feature/missing")
        third = self.sync()
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assert_ancestor(feature, self.remote_sha(self.fork, "custom"))

    def test_merge_conflict_preserves_remotes_and_retry_is_explicit(self) -> None:
        self.git("checkout", "custom")
        write(self.dev / "conflict.txt", "custom\n")
        custom = self.commit("custom conflict", "conflict.txt")
        self.git("push", "fork", "custom")
        main_before = self.remote_sha(self.fork, "main")

        self.git("checkout", "main")
        write(self.dev / "conflict.txt", "upstream\n")
        self.commit("upstream conflict", "conflict.txt")
        self.git("push", "upstream", "main")

        first = self.sync()
        self.assertNotEqual(first.returncode, 0)
        self.assertIn("merge failed", first.stderr)
        self.assertEqual(self.remote_sha(self.fork, "custom"), custom)
        self.assertEqual(self.remote_sha(self.fork, "main"), main_before)
        workspace = self.state / "workspace"
        self.assertEqual(command("git", "status", "--porcelain=v1", cwd=workspace).stdout, "")
        self.assertEqual(command("git", "rev-parse", "HEAD", cwd=workspace).stdout.strip(), custom)

        suppressed = self.sync()
        self.assertNotEqual(suppressed.returncode, 0)
        self.assertIn("previous failed attempt", suppressed.stderr)
        retried = self.sync(retry=True)
        self.assertNotEqual(retried.returncode, 0)
        self.assertIn("merge failed", retried.stderr)

    def test_feature_can_carry_an_upstream_conflict_resolution(self) -> None:
        self.git("checkout", "feature/one")
        write(self.dev / "conflict.txt", "feature\n")
        self.commit("feature edits shared code", "conflict.txt")
        self.git("push", "fork", "feature/one")
        initial = self.sync()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        previous_custom = self.remote_sha(self.fork, "custom")

        self.git("checkout", "main")
        write(self.dev / "conflict.txt", "upstream\n")
        upstream = self.commit("upstream edits same code", "conflict.txt")
        self.git("push", "upstream", "main")
        blocked = self.sync()
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(self.remote_sha(self.fork, "custom"), previous_custom)

        self.git("checkout", "feature/one")
        conflict = command("git", "merge", "--no-ff", "--no-edit", "main", cwd=self.dev, check=False)
        self.assertNotEqual(conflict.returncode, 0)
        write(self.dev / "conflict.txt", "feature and upstream reconciled\n")
        resolved = self.commit("reconcile upstream in feature branch", "conflict.txt")
        self.git("push", "fork", "feature/one")
        integrated = self.sync()
        self.assertEqual(integrated.returncode, 0, integrated.stderr)
        self.assertEqual(self.remote_file("custom", "conflict.txt"), "feature and upstream reconciled\n")
        self.assert_ancestor(resolved, self.remote_sha(self.fork, "custom"))
        self.assert_ancestor(upstream, self.remote_sha(self.fork, "custom"))

    def test_failed_validator_leaves_remote_unchanged(self) -> None:
        validator = self.make_validator("echo validation-broke >&2\nexit 23\n")
        custom = self.remote_sha(self.fork, "custom")
        main = self.remote_sha(self.fork, "main")
        result = self.sync(validator=validator)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("validator failed", result.stderr)
        self.assertIn("validation-broke", result.stdout)
        self.assertIn("validation finished with exit code 23", result.stdout)
        self.assertEqual(self.remote_sha(self.fork, "custom"), custom)
        self.assertEqual(self.remote_sha(self.fork, "main"), main)
        attempt = json.loads((self.state / "attempt.json").read_text())
        validation_log = self.state / "validation.log"
        self.assertEqual(attempt["validator_exit_code"], 23)
        self.assertEqual(attempt["validation_log"], str(validation_log))
        self.assertNotIn("validator_stdout", attempt)
        self.assertNotIn("validator_stderr", attempt)
        log = validation_log.read_text()
        self.assertIn("validation-broke", log)
        self.assertIn("validation finished with exit code 23", log)

    def test_validator_tracked_edits_are_preserved_and_block_next_run(self) -> None:
        validator = self.make_validator("printf 'changed\\n' > \"$1/base.txt\"\n")
        custom = self.remote_sha(self.fork, "custom")
        first = self.sync(validator=validator)
        self.assertNotEqual(first.returncode, 0)
        self.assertIn("changes preserved", first.stderr)
        self.assertEqual(self.remote_sha(self.fork, "custom"), custom)
        self.assertEqual((self.state / "workspace" / "base.txt").read_text(), "changed\n")
        second = self.sync()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("refusing to discard tracked changes", second.stderr)

    def test_concurrent_custom_update_from_validator_is_not_overwritten(self) -> None:
        concurrent = self.root / "concurrent"
        validator = self.make_validator(
            "git clone --quiet --branch custom "
            f"{shlex.quote(str(self.fork))} {shlex.quote(str(concurrent))}\n"
            f"git -C {shlex.quote(str(concurrent))} config user.name Concurrent\n"
            f"git -C {shlex.quote(str(concurrent))} config user.email concurrent@example.invalid\n"
            f"printf 'concurrent\\n' > {shlex.quote(str(concurrent / 'concurrent.txt'))}\n"
            f"git -C {shlex.quote(str(concurrent))} add concurrent.txt\n"
            f"git -C {shlex.quote(str(concurrent))} commit --quiet -m concurrent\n"
            f"git -C {shlex.quote(str(concurrent))} push --quiet origin HEAD:custom\n"
        )
        old_custom = self.remote_sha(self.fork, "custom")
        result = self.sync(validator=validator)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("remote inputs changed", result.stderr)
        attempt = json.loads((self.state / "attempt.json").read_text())
        self.assertEqual(attempt["validator_exit_code"], 0)
        self.assertEqual(attempt["validation_log"], str(self.state / "validation.log"))
        new_custom = self.remote_sha(self.fork, "custom")
        self.assertNotEqual(new_custom, old_custom)
        self.assertEqual(self.remote_file("custom", "concurrent.txt"), "concurrent\n")
        self.assertFalse(
            command(
                "git",
                "--git-dir",
                self.fork,
                "merge-base",
                "--is-ancestor",
                self.remote_sha(self.fork, "feature/one"),
                new_custom,
                check=False,
            ).returncode
            == 0
        )

    def test_divergent_fork_main_is_refused(self) -> None:
        self.git("checkout", "main")
        write(self.dev / "fork-main-only.txt", "divergent\n")
        divergent = self.commit("diverge fork main", "fork-main-only.txt")
        self.git("push", "fork", "main")
        custom = self.remote_sha(self.fork, "custom")
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fork/main is not an ancestor", result.stderr)
        self.assertEqual(self.remote_sha(self.fork, "main"), divergent)
        self.assertEqual(self.remote_sha(self.fork, "custom"), custom)

    def test_dirty_workspace_is_refused(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        write(self.state / "workspace" / "base.txt", "dirty\n")
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to discard tracked changes", result.stderr)

    def test_duplicate_reserved_and_invalid_manifest_entries_fail(self) -> None:
        cases = [
            ("feature/one\nfeature/one\n", "duplicate feature branch"),
            ("main\n", "reserved branch"),
            ("HEAD\n", "reserved branch"),
            ("bad branch\n", "invalid feature branch"),
            ("@{-1}\n", "invalid feature branch"),
            ("refs/heads/feature/one\n", "invalid feature branch"),
            ("remotes/fork/feature/one\n", "invalid feature branch"),
        ]
        for index, (manifest, expected) in enumerate(cases):
            with self.subTest(manifest=manifest):
                if index:
                    # A changed custom SHA makes this a new input rather than a suppressed retry.
                    self.git("checkout", "custom")
                custom = self.update_custom_manifest(manifest)
                result = self.sync()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
                self.assertEqual(self.remote_sha(self.fork, "custom"), custom)

    def test_unowned_nonempty_state_is_refused(self) -> None:
        self.state.mkdir()
        write(self.state / "someone-elses-file", "keep\n")
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unowned state directory", result.stderr)
        self.assertEqual((self.state / "someone-elses-file").read_text(), "keep\n")

    def test_second_run_exits_harmlessly_when_locked(self) -> None:
        self.state.mkdir()
        with (self.state / "lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("holds the state lock", result.stdout)
        self.assertFalse((self.state / ".sync-custom-owned").exists())


if __name__ == "__main__":
    unittest.main()
