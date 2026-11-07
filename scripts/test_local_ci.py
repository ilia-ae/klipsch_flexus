#!/usr/bin/env python3
"""Tests for scripts/local_ci.py and scripts/verify_local_ci.py.

Standard library only; run with ``python3 -I scripts/test_local_ci.py``.
Every key is a throwaway ed25519 key made in a temp dir; git runs with an
empty global config and no SSH agent, so the owner's YubiKey is never used.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def _load(name: str):
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"_test_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


L = _load("local_ci")
V = L.V  # the verifier instance the runner uses, so exception classes match

POLICY = {
    "schema": 2,
    "repository": V.REPOSITORY,
    "steps": [
        {"id": "first", "command": ["sh", "-c", "echo first step"], "timeout": 30},
        {
            "id": "second",
            "command": ["sh", "-c", "echo second step; echo '7 passed in 0.1s'"],
            "timeout": 30,
            "summary": {"pattern": "^(?P<count>\\d+) passed in ", "format": "$count passed"},
        },
    ],
    "tools": {"shell": ["sh", "-c", "echo fake-tool 1.0"]},
}


def sh(*args: str, cwd: Path | None = None, data: bytes | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, input=data, capture_output=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"{args} failed: {result.stderr.decode(errors='replace')}")
    return result.stdout.decode().strip()


class Fixture(unittest.TestCase):
    """A throwaway repository with an owner key, a foreign key and allowed signers."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.saved_env = dict(os.environ)
        cls.tmp = tempfile.TemporaryDirectory(prefix="klipsch-flexus-test-")
        base = Path(cls.tmp.name)
        (base / "gitconfig").write_text("")
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "SSH_AUTH_SOCK", "GITHUB_ACTIONS"):
            os.environ.pop(name, None)
        os.environ.update(GIT_CONFIG_GLOBAL=str(base / "gitconfig"), GIT_CONFIG_NOSYSTEM="1")
        cls.owner = base / "owner"
        cls.foe = base / "foe"
        for key in (cls.owner, cls.foe):
            sh("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", key.name, "-f", str(key))
        public = " ".join(Path(f"{cls.owner}.pub").read_text().split()[:2])
        cls.allowed = f"{V.PRINCIPAL} {public}\n"
        os.environ["LOCAL_CI_ALLOWED_SIGNERS"] = cls.allowed

    @classmethod
    def tearDownClass(cls) -> None:
        os.environ.clear()
        os.environ.update(cls.saved_env)
        cls.tmp.cleanup()

    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory(prefix="repo-", dir=self.tmp.name)
        self.repo = Path(self.dir.name) / "work"
        self.repo.mkdir()
        self.git("init", "--quiet", "--initial-branch=main")
        for key, value in (
            ("user.name", "Test Owner"),
            ("user.email", V.PRINCIPAL),
            ("gpg.format", "ssh"),
            ("gpg.ssh.program", "ssh-keygen"),
            ("user.signingkey", str(self.owner)),
            ("commit.gpgsign", "false"),
            ("tag.gpgsign", "false"),
        ):
            self.git("config", key, value)
        self.write_policy(POLICY)
        (self.repo / ".gitignore").write_text(".local-ci/\n")
        (self.repo / "README").write_text("fixture\n")
        self.git("add", "-A")
        self.sha = self.commit("initial")

    def tearDown(self) -> None:
        self.dir.cleanup()

    # helpers ---------------------------------------------------------------

    def git(self, *args: str, data: bytes | None = None) -> str:
        return sh("git", "-C", str(self.repo), *args, data=data)

    def write_policy(self, policy: dict) -> None:
        (self.repo / ".ci").mkdir(exist_ok=True)
        (self.repo / ".ci" / "local-ci.json").write_text(json.dumps(policy, indent=2) + "\n")

    def commit(self, message: str, key: Path | None = "owner") -> str:
        args = ["commit", "--quiet", "--allow-empty", "-m", message]
        if key is None:
            args.append("--no-gpg-sign")
        else:
            key = self.owner if key == "owner" else key
            args = ["-c", f"user.signingkey={key}", *args, "-S"]
        self.git(*args)
        return self.git("rev-parse", "HEAD")

    def run_ci(self, **kwargs) -> int:
        with contextlib.redirect_stderr(io.StringIO()):
            return L.run(self.repo, self.repo, **kwargs)

    def sign_ci(self, sha: str) -> bytes:
        with contextlib.redirect_stderr(io.StringIO()):
            L.sign(self.repo, self.repo, sha)
        return (self.repo / ".local-ci" / sha / "note").read_bytes()

    def evidence(self, sha: str | None = None) -> dict:
        """A valid evidence dict for ``sha`` without running anything."""
        sha = sha or self.git("rev-parse", "HEAD")
        policy_raw = self.git_bytes("cat-file", "blob", f"{sha}:.ci/local-ci.json")
        policy = json.loads(policy_raw)
        steps = [
            {
                "id": step["id"],
                "command": step["command"],
                "status": "passed",
                "exit_code": 0,
                "duration_ms": 5,
                "log_sha256": "0" * 64,
                "log_bytes": 0,
                "summary": None,
            }
            for step in policy["steps"]
        ]
        return {
            "schema": V.SCHEMA,
            "repository": V.REPOSITORY,
            "commit": sha,
            "tree": self.git("rev-parse", f"{sha}^{{tree}}"),
            "policy_sha256": hashlib.sha256(policy_raw).hexdigest(),
            "commit_signature": "owner",
            "steps": steps,
            "tools": {"git": "git version test"},
            "host": {"os": "Test", "release": "1", "arch": "x", "python": "3"},
            "created_at": "2026-11-07T00:00:00Z",
            "result": "passed",
        }

    def git_bytes(self, *args: str) -> bytes:
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, check=True).stdout

    def signed(self, payload: dict | bytes, key: Path | None = None, namespace: str = V.NAMESPACE) -> bytes:
        raw = payload if isinstance(payload, bytes) else V.canonical(payload)
        with tempfile.TemporaryDirectory(dir=self.dir.name) as folder:
            path = Path(folder) / "evidence"
            path.write_bytes(raw)
            sh("ssh-keygen", "-q", "-Y", "sign", "-n", namespace, "-f", str(key or self.owner), str(path))
            return raw + b"\n" + Path(f"{path}.sig").read_bytes()

    def attach(self, sha: str, note: bytes) -> None:
        blob = self.git("hash-object", "-w", "--stdin", data=note)
        self.git("notes", "--ref", V.NOTES_REF, "add", "-f", "-C", blob, sha)

    def verify(self, sha: str, **kwargs) -> dict:
        return V.verify(self.repo, sha, self.allowed, **kwargs)

    def assertRejected(self, fragment: str, sha: str, **kwargs) -> None:
        with self.assertRaises(V.Rejected) as caught:
            self.verify(sha, **kwargs)
        self.assertIn(fragment, str(caught.exception))


class AcceptTests(Fixture):
    def test_run_sign_verify_accepts(self) -> None:
        self.assertEqual(self.run_ci(), 0)
        note = self.sign_ci(self.sha)
        self.attach(self.sha, note)
        evidence = self.verify(self.sha)
        self.assertEqual(evidence["commit"], self.sha)
        self.assertEqual([s["status"] for s in evidence["steps"]], ["passed", "passed"])
        self.assertEqual(evidence["tools"]["shell"], "fake-tool 1.0")
        self.assertEqual([s["summary"] for s in evidence["steps"]], [None, "7 passed"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(V.main(["--sha", self.sha, "--repo", str(self.repo)]), 0)

    def test_publish_to_remote_and_verify_from_fresh_clone(self) -> None:
        remote = Path(self.dir.name) / "remote.git"
        sh("git", "init", "--quiet", "--bare", str(remote))
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "--quiet", "origin", "main")
        self.assertEqual(self.run_ci(), 0)
        self.sign_ci(self.sha)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(L.publish(self.repo, self.repo, self.sha, remote="origin", dispatch=False), 0)
        clone = Path(self.dir.name) / "ci"
        sh("git", "clone", "--quiet", str(remote), str(clone))
        with contextlib.redirect_stdout(io.StringIO()):
            code = V.main(["--sha", self.sha, "--repo", str(clone), "--fetch", "origin", "--wait", "0"])
        self.assertEqual(code, 0)

    def test_local_verify_uses_unpublished_note(self) -> None:
        self.assertEqual(self.run_ci(), 0)
        self.sign_ci(self.sha)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(L.verify(self.repo, self.repo, self.sha), 0)

    def test_signed_annotated_tag_accepted(self) -> None:
        self.attach(self.sha, self.signed(self.evidence()))
        self.git("tag", "-s", "v1.0.0", "-m", "v1.0.0")
        self.verify(self.sha, tag="v1.0.0")

    def test_external_pr_head_accepted_only_with_allow_external(self) -> None:
        sha = self.commit("contributor change", key=self.foe)
        self.assertEqual(self.run_ci(external=True), 0)
        note = self.sign_ci(sha)
        self.assertEqual(V.parse_note(note)[2]["commit_signature"], "external")
        self.attach(sha, note)
        self.verify(sha, allow_external=True)
        self.assertRejected("not an allowed signer", sha)


class RejectTests(Fixture):
    def test_unsigned_commit(self) -> None:
        sha = self.commit("unsigned", key=None)
        self.attach(sha, self.signed(self.evidence(sha)))
        self.assertRejected("unsigned", sha)

    def test_foreign_signed_commit(self) -> None:
        sha = self.commit("foreign", key=self.foe)
        self.attach(sha, self.signed(self.evidence(sha)))
        self.assertRejected("not an allowed signer", sha)

    def test_owner_claim_on_foreign_commit_even_with_allow_external(self) -> None:
        sha = self.commit("foreign", key=self.foe)
        self.attach(sha, self.signed(self.evidence(sha)))
        self.assertRejected("not an allowed signer", sha, allow_external=True)

    def test_external_evidence_in_strict_mode(self) -> None:
        evidence = self.evidence()
        evidence["commit_signature"] = "external"
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("external", self.sha)

    def test_missing_note(self) -> None:
        self.assertRejected(f"no signed local CI evidence for {self.sha}: run make ci && make ci-publish", self.sha)

    def test_tampered_evidence(self) -> None:
        note = self.signed(self.evidence())
        raw, _, signature = note.partition(b"\n")
        evidence = json.loads(raw)
        evidence["steps"][0]["duration_ms"] = 6
        self.attach(self.sha, V.canonical(evidence) + b"\n" + signature)
        self.assertRejected("signature", self.sha)

    def test_git_namespace_signature_cannot_be_replayed(self) -> None:
        self.attach(self.sha, self.signed(self.evidence(), namespace="git"))
        self.assertRejected("signature", self.sha)

    def test_foreign_key_evidence_signature(self) -> None:
        self.attach(self.sha, self.signed(self.evidence(), key=self.foe))
        self.assertRejected("signature", self.sha)

    def test_empty_allowed_signers(self) -> None:
        self.attach(self.sha, self.signed(self.evidence()))
        with self.assertRaises(V.Rejected) as caught:
            V.verify(self.repo, self.sha, "  \n# only a comment\n")
        self.assertIn("no allowed signers", str(caught.exception))

    def test_stale_evidence_for_another_commit(self) -> None:
        old = self.evidence()
        sha = self.commit("next")
        self.attach(sha, self.signed(old))
        self.assertRejected("stale evidence", sha)

    def test_stale_evidence_for_another_tree(self) -> None:
        old_tree = self.evidence()["tree"]
        (self.repo / "README").write_text("changed\n")
        self.git("add", "README")
        sha = self.commit("change tree")
        evidence = self.evidence(sha)
        evidence["tree"] = old_tree
        self.attach(sha, self.signed(evidence))
        self.assertRejected("tree", sha)

    def test_policy_changed(self) -> None:
        evidence = self.evidence()
        evidence["policy_sha256"] = "1" * 64
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("different .ci/local-ci.json", self.sha)

    def test_missing_step(self) -> None:
        evidence = self.evidence()
        del evidence["steps"][1]
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("lacks required step(s): second", self.sha)

    def test_new_policy_step_without_evidence(self) -> None:
        policy = json.loads(json.dumps(POLICY))
        policy["steps"].append({"id": "third", "command": ["true"]})
        self.write_policy(policy)
        self.git("add", "-A")
        sha = self.commit("require a third step")
        evidence = self.evidence(sha)
        del evidence["steps"][2]
        self.attach(sha, self.signed(evidence))
        self.assertRejected("lacks required step(s): third", sha)

    def test_failed_step(self) -> None:
        evidence = self.evidence()
        evidence["steps"][0].update(status="failed", exit_code=1)
        evidence["result"] = "failed"
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("first did not pass", self.sha)

    def test_passed_status_with_nonzero_exit(self) -> None:
        evidence = self.evidence()
        evidence["steps"][1]["exit_code"] = 3
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("second did not pass", self.sha)

    def test_failed_overall_result(self) -> None:
        evidence = self.evidence()
        evidence["result"] = "failed"
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("result is 'failed'", self.sha)

    def test_reordered_or_extra_steps(self) -> None:
        evidence = self.evidence()
        evidence["steps"].reverse()
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("do not match the policy", self.sha)
        evidence = self.evidence()
        evidence["steps"].append(dict(evidence["steps"][0], id="bonus"))
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("do not match the policy", self.sha)

    def test_different_command(self) -> None:
        evidence = self.evidence()
        evidence["steps"][0]["command"] = ["true"]
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("the policy requires", self.sha)

    def test_extra_field(self) -> None:
        evidence = self.evidence()
        evidence["comment"] = "trust me"
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("unexpected fields ['comment']", self.sha)
        evidence = self.evidence()
        evidence["steps"][0]["note"] = "x"
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("unexpected or missing fields", self.sha)

    def test_other_repository(self) -> None:
        evidence = self.evidence()
        evidence["repository"] = "someone/else"
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("repository", self.sha)

    def test_trailing_garbage_after_signature(self) -> None:
        self.attach(self.sha, self.signed(self.evidence()) + b"extra\n")
        self.assertRejected("nothing else", self.sha)

    def test_two_signatures(self) -> None:
        note = self.signed(self.evidence())
        self.attach(self.sha, note + note.partition(b"\n")[2])
        self.assertRejected("nothing else", self.sha)

    def test_non_canonical_json(self) -> None:
        raw = json.dumps(self.evidence(), sort_keys=True, separators=(", ", ": ")).encode()
        self.attach(self.sha, self.signed(raw))
        self.assertRejected("canonical", self.sha)

    def test_duplicate_key(self) -> None:
        raw = V.canonical(self.evidence())
        raw = raw[:-1] + b',"result":"passed"}'
        self.attach(self.sha, self.signed(raw))
        self.assertRejected("duplicate key", self.sha)

    def test_float(self) -> None:
        raw = V.canonical(self.evidence()).replace(b'"duration_ms":5', b'"duration_ms":5.5', 1)
        self.attach(self.sha, self.signed(raw))
        self.assertRejected("non-integer", self.sha)

    def test_unsigned_note(self) -> None:
        self.attach(self.sha, V.canonical(self.evidence()) + b"\n")
        self.assertRejected("exactly one SSH signature", self.sha)

    def test_short_or_unknown_sha(self) -> None:
        self.assertRejected("40-character", self.sha[:12])
        self.assertRejected("not in this repository", "f" * 40)

    def test_lightweight_tag(self) -> None:
        self.attach(self.sha, self.signed(self.evidence()))
        self.git("tag", "v1.0.0")
        self.assertRejected("not an annotated tag", self.sha, tag="v1.0.0")

    def test_unsigned_annotated_tag(self) -> None:
        self.attach(self.sha, self.signed(self.evidence()))
        self.git("tag", "-a", "--no-sign", "v1.0.0", "-m", "v1.0.0")
        self.assertRejected("not signed by an allowed signer", self.sha, tag="v1.0.0")

    def test_foreign_signed_tag(self) -> None:
        self.attach(self.sha, self.signed(self.evidence()))
        self.git("-c", f"user.signingkey={self.foe}", "tag", "-s", "v1.0.0", "-m", "v1.0.0")
        self.assertRejected("not signed by an allowed signer", self.sha, tag="v1.0.0")

    def test_tag_on_another_commit(self) -> None:
        self.git("tag", "-s", "v1.0.0", "-m", "v1.0.0")
        sha = self.commit("after the tag")
        self.attach(sha, self.signed(self.evidence(sha)))
        self.assertRejected("points at", sha, tag="v1.0.0")

    def test_cli_reports_failure(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(V.main(["--sha", self.sha, "--repo", str(self.repo)]), 1)
        self.assertIn("no signed local CI evidence", err.getvalue())

    def test_fetch_gives_up_after_wait(self) -> None:
        remote = Path(self.dir.name) / "remote.git"
        sh("git", "init", "--quiet", "--bare", str(remote))
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "--quiet", "origin", "main")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = V.main(["--sha", self.sha, "--repo", str(self.repo), "--fetch", "origin", "--wait", "1"])
        self.assertEqual(code, 1)
        self.assertIn("no signed local CI evidence", err.getvalue())


class RunnerTests(Fixture):
    def test_refuses_modified_tracked_file(self) -> None:
        (self.repo / "README").write_text("edited\n")
        with self.assertRaises(L.Failure) as caught:
            self.run_ci()
        self.assertIn("dirty tree", str(caught.exception))

    def test_refuses_any_untracked_file(self) -> None:
        for path in (
            "tests/test_new.py",
            "custom_components/x/new.py",
            ".ci/extra.json",
            "ansible/new.yml",
            "GNUmakefile",
            "pytest.ini",
            "conftest.py",
            "ruff.toml",
            "scratch.txt",
        ):
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n")
            with self.assertRaises(L.Failure, msg=path):
                self.run_ci()
            target.unlink()

    def test_refuses_unexpected_ignored_file(self) -> None:
        exclude = self.repo / ".git" / "info" / "exclude"
        exclude.write_text("GNUmakefile\nconftest.py\n")
        for path in ("GNUmakefile", "tests/conftest.py"):
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n")
            with self.assertRaises(L.Failure, msg=path) as caught:
                self.run_ci()
            self.assertIn("!! ", str(caught.exception))
            target.unlink()

    def test_tooling_and_caches_may_be_ignored(self) -> None:
        (self.repo / ".gitignore").write_text(".local-ci/\n.venv*\n__pycache__/\n/ansible/collections\n.molecule/\n")
        self.git("add", ".gitignore")
        self.sha = self.commit("ignore tooling")
        for path in (".venv-test/bin/python", "tests/__pycache__/x.pyc", "ansible/collections/x", ".molecule/s/state"):
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n")
        self.assertEqual(self.run_ci(), 0)

    def test_steps_get_a_scrubbed_environment(self) -> None:
        policy = json.loads(json.dumps(POLICY))
        probe = "echo MOLECULE=${MOLECULE-unset} MAKEFLAGS=${MAKEFLAGS-unset} SSH=${SSH_AUTH_SOCK-unset} CI=$LOCAL_CI"
        policy["steps"][0]["command"] = ["sh", "-c", probe]
        self.write_policy(policy)
        self.git("add", "-A")
        sha = self.commit("environment probe")
        saved = dict(os.environ)
        os.environ.update(MOLECULE="true", MAKEFLAGS="UVX=true", SSH_AUTH_SOCK="/tmp/agent.sock")
        try:
            self.assertEqual(self.run_ci(), 0)
        finally:
            os.environ.clear()
            os.environ.update(saved)
        log = (self.repo / ".local-ci" / sha / "logs" / "first.log").read_text()
        self.assertEqual(log.strip(), "MOLECULE=unset MAKEFLAGS=unset SSH=unset CI=1")

    def test_pr_confirm_gate(self) -> None:
        routine = [
            "custom_components/klipsch_flexus/api.py",
            "custom_components/klipsch_flexus/translations/de.json",
            "custom_components/klipsch_flexus/translations/zh-Hans.json",
            "custom_components/klipsch_flexus/brand/dark_icon@2x.png",
            "tests/test_api.py",
            "docs/TESTING.md",
            "README.md",
        ]
        machinery = [
            "tests/conftest.py",
            "custom_components/klipsch_flexus/conftest.py",
            "GNUmakefile",
            "Makefile",
            "mk/ansible.mk",
            "pyproject.toml",
            "pytest.ini",
            "setup.cfg",
            "ruff.toml",
            "requirements_test.txt",
            "requirements-dev.txt",
            ".github/ci/requirements_test_min.txt",
            ".github/workflows/local-ci.yaml",
            ".ci/local-ci.json",
            "scripts/local_ci.py",
            "ansible/requirements.yml",
            ".yamllint",
            ".ansible-lint",
            "tests/fixtures/data.json",
        ]
        self.assertEqual(L.machinery_changes(routine), [])
        self.assertEqual(L.machinery_changes(routine + machinery), machinery)

    def test_refuses_unsigned_head(self) -> None:
        self.commit("unsigned", key=None)
        with self.assertRaises(L.Failure) as caught:
            self.run_ci()
        self.assertIn("not signed", str(caught.exception))

    def test_failing_step_is_recorded_and_not_signed(self) -> None:
        policy = json.loads(json.dumps(POLICY))
        policy["steps"][0]["command"] = ["sh", "-c", "echo boom; exit 3"]
        self.write_policy(policy)
        self.git("add", "-A")
        sha = self.commit("failing step")
        self.assertEqual(self.run_ci(), 1)
        evidence = json.loads((self.repo / ".local-ci" / sha / "evidence.json").read_bytes())
        self.assertEqual(evidence["result"], "failed")
        self.assertEqual((evidence["steps"][0]["status"], evidence["steps"][0]["exit_code"]), ("failed", 3))
        self.assertEqual(evidence["steps"][1]["status"], "passed")
        with self.assertRaises(L.Failure):
            self.sign_ci(sha)

    def test_timeout_and_missing_program(self) -> None:
        policy = json.loads(json.dumps(POLICY))
        policy["steps"][0].update(command=["sh", "-c", "sleep 30"], timeout=1)
        policy["steps"][1]["command"] = ["/nonexistent/program"]
        self.write_policy(policy)
        self.git("add", "-A")
        sha = self.commit("slow step")
        self.assertEqual(self.run_ci(), 1)
        evidence = json.loads((self.repo / ".local-ci" / sha / "evidence.json").read_bytes())
        self.assertEqual([s["status"] for s in evidence["steps"]], ["timeout", "error"])

    def test_step_that_dirties_the_tree_voids_the_run(self) -> None:
        policy = json.loads(json.dumps(POLICY))
        policy["steps"][1]["command"] = ["sh", "-c", "echo changed > README"]
        self.write_policy(policy)
        self.git("add", "-A")
        self.commit("dirtying step")
        with self.assertRaises(L.Failure) as caught:
            self.run_ci()
        self.assertIn("changed HEAD or the working tree", str(caught.exception))

    def test_sign_refuses_changed_log(self) -> None:
        self.assertEqual(self.run_ci(), 0)
        (self.repo / ".local-ci" / self.sha / "logs" / "first.log").write_text("forged\n")
        with self.assertRaises(L.Failure) as caught:
            self.sign_ci(self.sha)
        self.assertIn("changed since the run", str(caught.exception))

    def test_sign_uses_dedicated_namespace(self) -> None:
        self.assertEqual(self.run_ci(), 0)
        note = self.sign_ci(self.sha)
        raw, signature, _ = V.parse_note(note)
        with tempfile.TemporaryDirectory(dir=self.dir.name) as folder:
            allowed = V.write_allowed_signers(self.allowed, folder)
            V.verify_signature(raw, signature, allowed)
            (Path(folder) / "sig").write_bytes(signature)
            as_git = subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", allowed, "-I", V.PRINCIPAL, "-n", "git", "-s", f"{folder}/sig"],
                input=raw,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(as_git.returncode, 0, "evidence signature must not verify as a git signature")

    def test_literal_key_signing_command_uses_agent_flag(self) -> None:
        public = Path(f"{self.owner}.pub").read_text().strip()
        self.git("config", "user.signingkey", f"key::{public}")
        self.git("config", "gpg.ssh.program", "/opt/signer")
        with tempfile.TemporaryDirectory(dir=self.dir.name) as folder:
            command = L.signing_command(self.repo, folder, Path(folder) / "payload")
            self.assertEqual(command[:5], ["/opt/signer", "-Y", "sign", "-n", V.NAMESPACE])
            self.assertIn("-U", command)
            self.assertEqual((Path(folder) / "signing_key.pub").read_text().strip(), public)


class SummaryTests(Fixture):
    """The runner's summary extraction and the verifier's strictness about it."""

    SPEC = {"pattern": r"^(?P<count>\d+) passed in ", "format": "$count passed"}

    def test_extract_formats_every_match(self) -> None:
        spec = {"pattern": r"^  (?:PASS|(?P<failed>FAIL))  r/(?P<name>[a-z]+)  \(", "format": "$failed $name"}
        log = "x\n  PASS  r/fresh  (test)\n  FAIL  r/upgrade  (test)\n  PASS  r/minimum  (test)\n"
        self.assertEqual(L.extract_summary(spec, log), "fresh, FAIL upgrade, minimum")

    def test_extract_whole_match_without_format(self) -> None:
        self.assertEqual(
            L.extract_summary({"pattern": r"^All checks passed"}, "a\nAll checks passed!\n"), "All checks passed"
        )
        spec = {"pattern": "^Invalid integrations: 0$", "format": "ok"}
        self.assertEqual(L.extract_summary(spec, "Invalid integrations: 0\n"), "ok")

    def test_extract_strips_colour_and_collapses_spaces(self) -> None:
        log = "\x1b[32m183   passed\x1b[0m in 9.6s\n"
        spec = {"pattern": r"^(?P<counts>\d+\s+passed) in ", "format": "$counts"}
        self.assertEqual(L.extract_summary(spec, log), "183 passed")

    def test_no_spec_or_no_match_gives_none(self) -> None:
        self.assertIsNone(L.extract_summary(None, "183 passed in 1s\n"))
        self.assertIsNone(L.extract_summary(self.SPEC, "2 failed in 1s\n"))

    def test_unsafe_or_long_output_gives_none(self) -> None:
        self.assertIsNone(L.extract_summary({"pattern": r"^<.*>$"}, "<img src=x>\n"))
        self.assertIsNone(L.extract_summary({"pattern": r"^\S+$"}, "café\n"))
        self.assertIsNone(L.extract_summary({"pattern": r"^x+$"}, "x" * (V.MAX_SUMMARY + 1) + "\n"))
        self.assertIsNone(L.extract_summary({"pattern": r"^.+$"}, "a | b\n"))

    def test_matches_are_capped(self) -> None:
        log = "".join(f"t{i}\n" for i in range(50))
        self.assertEqual(L.extract_summary({"pattern": r"^t\d+$"}, log).count(", "), L.MAX_SUMMARY_MATCHES - 1)

    def test_valid_summary(self) -> None:
        for good in ("183 passed", "fresh, upgrade, minimum", "ok", "1 failure(s), 2 warning(s) 95%"):
            self.assertTrue(V.valid_summary(good), good)
        for bad in ("", " ok", "ok ", "a  b", "a\nb", "[x](y)", "`x`", "<b>", "a|b", "café", "x" * 121, 5, None):
            self.assertFalse(V.valid_summary(bad), bad)

    def test_policy_rejects_bad_summary_specs(self) -> None:
        for spec, fragment in (
            ("183 passed", "must be"),
            ({"pattern": "x", "template": "y"}, "must be"),
            ({"format": "ok"}, "must be"),
            ({"pattern": ""}, "invalid pattern"),
            ({"pattern": "x" * (V.MAX_SUMMARY_PATTERN + 1)}, "invalid pattern"),
            ({"pattern": "(unclosed"}, "does not compile"),
            ({"pattern": "(?P<n>x)", "format": "$other"}, "groups of its pattern"),
            ({"pattern": "(?P<n>x)", "format": "$"}, "groups of its pattern"),
            ({"pattern": "x", "format": ""}, "invalid format"),
        ):
            policy = json.loads(json.dumps(POLICY))
            policy["steps"][0]["summary"] = spec
            with self.assertRaises(V.Rejected, msg=spec) as caught:
                V.load_policy(json.dumps(policy).encode())
            self.assertIn(fragment, str(caught.exception), spec)

    def test_old_policy_schema_rejected(self) -> None:
        policy = dict(POLICY, schema=1)
        with self.assertRaises(V.Rejected):
            V.load_policy(json.dumps(policy).encode())

    def test_old_evidence_schema_rejected(self) -> None:
        evidence = self.evidence()
        evidence["schema"] = "klipsch-flexus-local-ci/1"
        for step in evidence["steps"]:
            del step["summary"]
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("is not klipsch-flexus-local-ci/2", self.sha)

    def test_verifier_accepts_safe_summary_for_declared_step(self) -> None:
        evidence = self.evidence()
        evidence["steps"][1]["summary"] = "7 passed, 1 skipped"
        self.attach(self.sha, self.signed(evidence))
        self.assertEqual(self.verify(self.sha)["steps"][1]["summary"], "7 passed, 1 skipped")

    def test_verifier_rejects_bad_summaries(self) -> None:
        for index, value in (
            (1, "<img src=x onerror=alert(1)>"),
            (1, "x" * (V.MAX_SUMMARY + 1)),
            (1, "7 passed\n"),
            (1, " 7 passed"),
            (1, "!["),
            (1, ""),
            (1, 7),
            (1, ["7 passed"]),
            (0, "7 passed"),  # the policy declares no summary for step "first"
        ):
            evidence = self.evidence()
            evidence["steps"][index]["summary"] = value
            self.attach(self.sha, self.signed(evidence))
            self.assertRejected("malformed summary", self.sha)

    def test_verifier_requires_the_summary_field(self) -> None:
        evidence = self.evidence()
        del evidence["steps"][0]["summary"]
        self.attach(self.sha, self.signed(evidence))
        self.assertRejected("unexpected or missing fields", self.sha)


BADGE_POLICY = {
    "schema": 2,
    "repository": V.REPOSITORY,
    "steps": [
        {"id": step_id, "command": ["true"], "summary": {"pattern": "x"}}
        for step_id in ("pytest-latest", "pytest-min", "hassfest", "molecule")
    ],
}


class BadgeTests(Fixture):
    """badge_files: verified evidence -> shields.io endpoint files for ci-results."""

    def badge_commit(self, summaries: dict[str, str | None], tools: dict[str, str] | None = None) -> bytes:
        self.write_policy(BADGE_POLICY)
        self.git("add", "-A")
        self.sha = self.commit("badge policy")
        evidence = self.evidence()
        for step in evidence["steps"]:
            step["summary"] = summaries.get(step["id"])
        evidence["tools"].update(tools or {})
        evidence["created_at"] = "2026-11-01T12:34:56Z"
        note = self.signed(evidence)
        self.attach(self.sha, note)
        self.verify(self.sha)  # badge_files is only ever fed verified notes
        return note

    def test_files_from_verified_evidence(self) -> None:
        note = self.badge_commit(
            {
                "pytest-latest": "183 passed",
                "pytest-min": "183 passed, 2 skipped",
                "hassfest": "ok",
                "molecule": "fresh, upgrade, minimum",
            },
            {"homeassistant-latest": "2026.10.4", "homeassistant-min": "2024.11.0"},
        )
        files = V.badge_files(note, "# comment\n" + self.allowed)
        sha = self.sha
        self.assertEqual(
            sorted(files),
            sorted(
                [
                    "README.md",
                    "allowed_signers",
                    "badges/hassfest.json",
                    "badges/molecule.json",
                    "badges/pytest-latest.json",
                    "badges/pytest-min.json",
                    "badges/signed.json",
                    "evidence/latest.json",
                    "evidence/latest.json.sig",
                    f"evidence/{sha}.json",
                    f"evidence/{sha}.json.sig",
                ]
            ),
        )
        badge = {
            name: json.loads(files[f"badges/{name}.json"])
            for name in ("pytest-latest", "pytest-min", "hassfest", "molecule", "signed")
        }
        self.assertEqual(
            {name: (b["label"], b["message"]) for name, b in badge.items()},
            {
                "pytest-latest": ("pytest", "HA 2026.10 · 183 passed"),
                "pytest-min": ("pytest", "HA 2024.11 · 183 passed · 2 skipped"),
                "hassfest": ("hassfest", "ok"),
                "molecule": ("molecule", "fresh · upgrade · minimum"),
                "signed": ("local CI", f"signed · {sha[:7]} · 2026-11-01"),
            },
        )
        for b in badge.values():
            self.assertEqual((b["schemaVersion"], b["color"], len(b)), (1, "brightgreen", 4))
        raw, signature, _ = V.parse_note(note)
        self.assertEqual(files["evidence/latest.json"], raw)
        self.assertEqual(files[f"evidence/{sha}.json.sig"], signature)
        self.assertEqual(files["allowed_signers"].decode(), self.allowed)
        # the published pair verifies with plain ssh-keygen, as docs/TESTING.md says
        with tempfile.TemporaryDirectory(dir=self.dir.name) as folder:
            V.write_files(folder, files)
            result = subprocess.run(
                [
                    "ssh-keygen",
                    "-Y",
                    "verify",
                    "-f",
                    f"{folder}/allowed_signers",
                    "-I",
                    V.PRINCIPAL,
                    "-n",
                    V.NAMESPACE,
                    "-s",
                    f"{folder}/evidence/latest.json.sig",
                ],
                input=Path(folder, "evidence", "latest.json").read_bytes(),
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_summary_or_odd_version_falls_back(self) -> None:
        note = self.badge_commit({"pytest-latest": None}, {"homeassistant-latest": "unavailable (exit 1): $(rm -rf ~)"})
        files = V.badge_files(note, self.allowed)
        self.assertEqual(json.loads(files["badges/pytest-latest.json"])["message"], "passed")
        self.assertNotIn("homeassistant-min", self.evidence()["tools"])
        self.assertEqual(json.loads(files["badges/pytest-min.json"])["message"], "passed")

    def test_badge_only_for_steps_in_the_evidence(self) -> None:
        note = self.signed(self.evidence())  # POLICY: steps first/second, no badge steps
        self.attach(self.sha, note)
        files = V.badge_files(note, self.allowed)
        self.assertEqual(sorted(name for name in files if name.startswith("badges/")), ["badges/signed.json"])

    def test_refuses_external_evidence(self) -> None:
        evidence = self.evidence()
        evidence["commit_signature"] = "external"
        with self.assertRaises(V.Rejected):
            V.badge_files(self.signed(evidence), self.allowed)

    def test_write_files_stays_inside(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.dir.name) as folder:
            with self.assertRaises(V.Rejected):
                V.write_files(folder, {"../escape.json": b"{}"})
            self.assertFalse(Path(folder).parent.joinpath("escape.json").exists())

    def test_cli_writes_badges_after_verification(self) -> None:
        self.badge_commit({"pytest-latest": "183 passed"}, {"homeassistant-latest": "2026.10.4"})
        out = Path(self.dir.name) / "ci-results"
        with contextlib.redirect_stdout(io.StringIO()):
            code = V.main(["--sha", self.sha, "--repo", str(self.repo), "--write-badges", str(out)])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads((out / "badges/pytest-latest.json").read_text())["message"], "HA 2026.10 · 183 passed"
        )
        self.assertTrue((out / "evidence" / f"{self.sha}.json.sig").is_file())

    def test_cli_writes_nothing_when_verification_fails(self) -> None:
        out = Path(self.dir.name) / "ci-results"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(V.main(["--sha", self.sha, "--repo", str(self.repo), "--write-badges", str(out)]), 1)
            self.attach(self.sha, self.signed(self.evidence()))
            args = ["--sha", self.sha, "--repo", str(self.repo), "--write-badges", str(out), "--allow-external"]
            self.assertEqual(V.main(args), 1)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
