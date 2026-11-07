#!/usr/bin/env python3
"""Local CI for klipsch_flexus: run the policy, sign the evidence, publish it.

All CI runs on the owner's Mac. GitHub only verifies the result
(scripts/verify_local_ci.py). Standard library only; run with ``python3 -I``.

  run      run every step of .ci/local-ci.json on a clean, committed tree and
           write canonical JSON evidence (logs stay in .local-ci/<sha>/)
  sign     sign the evidence with the git signing key (ssh-keygen -Y sign via
           gpg.ssh.program, namespace klipsch-flexus-local-ci@ilia.ae) and
           check the fresh signature before keeping it
  verify   the remote verifier's checks, locally (note, or the unpublished one)
  publish  attach the signed evidence as a git note in refs/notes/local-ci and
           push only that ref; --dispatch also asks GitHub to verify the commit
  pr       test a pull request head in a temporary worktree with this
           (trusted) runner and the PR's own freshly built tooling, then sign,
           publish and dispatch verification (not a sandbox: review first)
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path


def _load_verifier():
    path = Path(__file__).resolve().with_name("verify_local_ci.py")
    spec = importlib.util.spec_from_file_location("verify_local_ci", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V = _load_verifier()
Rejected = V.Rejected

STATE_DIR = ".local-ci"
SIGN_TIMEOUT = 60
MAX_SUMMARY_MATCHES = 20
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# Ignored paths a clean checkout may hold: local tooling, caches and the state
# of this runner. Any other ignored file (a GNUmakefile, pytest.ini, conftest.py
# hidden by a global excludes file, ...) could change what a step does without
# changing the commit, so it makes the tree dirty, like any untracked file.
IGNORED_OK = (
    ".venv",  # .venv, .venv-test, .venv-testmin (directories or symlinks)
    ".local-ci/",
    ".molecule/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".claude/",
    ".reverse/",
    ".coverage",
    "ansible/collections",
)
IGNORED_OK_NAMES = ("__pycache__", ".DS_Store")
# The only variables a step inherits. Everything else (MAKEFLAGS carrying
# `make ci UVX=true`, MOLECULE, MOLECULE_ARGS, IMAGES, PYTHON, ANSIBLE_*,
# tokens, SSH_AUTH_SOCK) could change what a step does, or hand it credentials,
# without changing its recorded command.
STEP_ENV = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "TERM",
    "LANG",
    "DOCKER_HOST",
    "DOCKER_CONTEXT",
    "DOCKER_CONFIG",
    "DOCKER_CERT_PATH",
    "DOCKER_TLS_VERIFY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "__CF_USER_TEXT_ENCODING",
)
# A pull request whose changes all match these needs no CONFIRM: integration
# code, test modules and documentation. Anything else (a conftest.py, any
# makefile, pyproject.toml, requirements, .ci/, scripts/, ansible/, .github/,
# lint configuration, a new top-level file) can change what the policy's steps
# do, so the owner must review it and pass CONFIRM=1.
PR_ROUTINE = (
    r"custom_components/klipsch_flexus/(?:[a-z0-9_]+\.py|[a-z0-9_]+\.json|translations/[A-Za-z_-]+\.json|brand/[a-z0-9_@]+\.png)",
    r"tests/test_[a-z0-9_]+\.py",
    r"(?:README|CHANGELOG)\.md|docs/[A-Za-z0-9_./-]+\.(?:md|png|svg)",
)


class Failure(Exception):
    """The runner refuses to continue."""


def say(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def git(root: Path, *args: str, data: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", "-C", str(root), *args], input=data, capture_output=True, check=False)
    if check and result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise Failure(f"git {' '.join(args[:2])} failed: {detail}")
    return result


def git_text(root: Path, *args: str, data: bytes | None = None) -> str:
    return git(root, *args, data=data).stdout.decode().strip()


def toplevel(path: str | None) -> Path:
    return Path(git_text(Path(path or "."), "rev-parse", "--show-toplevel"))


def resolve(root: Path, rev: str) -> str:
    return git_text(root, "rev-parse", "--verify", f"{rev}^{{commit}}")


def _ignored_ok(path: str) -> bool:
    if any(part in IGNORED_OK_NAMES for part in path.rstrip("/").split("/")):
        return True
    return any(path == p or path.startswith(p) for p in IGNORED_OK)


def dirty_paths(root: Path) -> list[str]:
    """Tracked changes, untracked files and unexpected ignored files, anywhere."""
    raw = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=normal", "--ignored=matching").stdout.decode()
    entries = raw.split("\0")
    dirty, index = [], 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":
            index += 1  # -z puts the rename source in the next entry
        if code == "!!" and _ignored_ok(path):
            continue
        dirty.append(f"{code} {path}")
    return dirty


def step_env(sha: str) -> dict:
    env = {name: value for name, value in os.environ.items() if name in STEP_ENV or name.startswith("LC_")}
    env.update(LOCAL_CI="1", LOCAL_CI_SHA=sha)
    return env


def require_clean(root: Path) -> None:
    dirty = dirty_paths(root)
    if dirty:
        listing = "\n  ".join(dirty[:20])
        raise Failure(
            "refusing to run on a dirty tree; commit, stash or delete these first "
            f"(ignored files count too, except local tooling and caches):\n  {listing}"
        )


def allowed_signers_text(root: Path) -> str:
    """Local trust root: LOCAL_CI_ALLOWED_SIGNERS, else git's allowed signers file."""
    text = os.environ.get("LOCAL_CI_ALLOWED_SIGNERS")
    if text:
        return text
    configured = git(root, "config", "--get", "gpg.ssh.allowedSignersFile", check=False).stdout.decode().strip()
    path = Path(os.path.expanduser(configured or "~/.ssh/allowed_signers"))
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        raise Failure(f"no allowed signers: set LOCAL_CI_ALLOWED_SIGNERS or create {path}") from None


def commit_is_owner_signed(root: Path, sha: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="klipsch-flexus-ci-") as folder:
        allowed = V.write_allowed_signers(allowed_signers_text(root), folder)
        try:
            V.verify_commit_signature(root, sha, allowed)
        except Rejected:
            return False
    return True


def state_dir(state_root: Path, sha: str) -> Path:
    return state_root / STATE_DIR / sha


def sha256_file(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def run_step(step: dict, root: Path, log: Path, env: dict) -> tuple[str, int | None]:
    timeout = step.get("timeout", 1800)
    with log.open("wb") as stream:
        try:
            process = subprocess.Popen(
                step["command"],
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as error:
            stream.write(f"local_ci: cannot start {step['command'][0]}: {error}\n".encode())
            return "error", None
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _stop(process)
            stream.flush()
            stream.write(f"\nlocal_ci: step timed out after {timeout} s\n".encode())
            return "timeout", None
        except KeyboardInterrupt:
            _stop(process)
            raise
    return ("passed" if code == 0 else "failed"), code


def extract_summary(spec: dict | None, log_text: str, step_id: str = "step") -> str | None:
    """The step's short summary from its log, per the policy's ``summary`` spec.

    Every match of ``pattern`` (multiline) gives one part: ``format`` with its
    ``$name`` groups filled in (an unmatched group is empty), or the whole
    match. Parts are joined with ", ". The result must pass the verifier's
    ``valid_summary`` (short, plain ASCII), else the step has no summary.
    """
    if spec is None:
        return None
    pattern, template = V.summary_spec(spec, step_id)
    parts = []
    for match in pattern.finditer(ANSI_RE.sub("", log_text)):
        if template is None:
            part = match.group(0)
        else:
            part = template.substitute({name: value or "" for name, value in match.groupdict().items()})
        part = " ".join(part.split())
        if part:
            parts.append(part)
        if len(parts) >= MAX_SUMMARY_MATCHES:
            break
    summary = ", ".join(parts)
    return summary if V.valid_summary(summary) else None


def _stop(process: subprocess.Popen) -> None:
    for sig, grace in ((signal.SIGTERM, 20), (signal.SIGKILL, 10)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue


def tool_versions(policy: dict, root: Path, env: dict) -> dict:
    tools = {"git": git_text(root, "--version")}
    for name, command in policy.get("tools", {}).items():
        try:
            result = subprocess.run(
                command, cwd=root, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=120, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            tools[name] = f"unavailable ({type(error).__name__})"
            continue
        text = (result.stdout or result.stderr).decode(errors="replace").strip()
        first = text.splitlines()[0] if text else ""
        tools[name] = (
            first[:300] if result.returncode == 0 else f"unavailable (exit {result.returncode}): {first[:200]}"
        )
    return tools


def run(root: Path, state_root: Path, *, external: bool = False) -> int:
    require_clean(root)
    sha = resolve(root, "HEAD")
    tree = git_text(root, "rev-parse", f"{sha}^{{tree}}")
    policy_raw = git(root, "cat-file", "blob", f"{sha}:{V.POLICY_PATH}").stdout
    policy = V.load_policy(policy_raw)
    if commit_is_owner_signed(root, sha):
        trust = "owner"
    elif external:
        trust = "external"
    else:
        raise Failure(
            f"HEAD {sha} is not signed by an allowed signer for {V.PRINCIPAL}; sign it (git commit -S) "
            "or, for someone else's pull request, use make ci-pr PR=<n>"
        )

    out = state_dir(state_root, sha)
    shutil.rmtree(out, ignore_errors=True)
    (out / "logs").mkdir(parents=True)
    env = step_env(sha)
    steps = policy["steps"]
    results = []
    say(f"local CI for {sha} ({len(steps)} steps); logs in {out / 'logs'}")
    for number, step in enumerate(steps, 1):
        log = out / "logs" / f"{step['id']}.log"
        say(f"==> [{number}/{len(steps)}] {step['id']}: {' '.join(step['command'])}")
        started = time.monotonic()
        status, code = run_step(step, root, log, env)
        duration_ms = int((time.monotonic() - started) * 1000)
        digest, size = sha256_file(log)
        summary = extract_summary(step.get("summary"), log.read_bytes().decode("utf-8", errors="replace"), step["id"])
        note = f": {summary}" if summary else (" (no summary found in the log)" if "summary" in step else "")
        say(f"<== {step['id']}: {status} (exit {code}) in {duration_ms / 1000:.1f} s{note}")
        if status != "passed":
            tail = log.read_bytes()[-4000:].decode(errors="replace").splitlines()[-25:]
            say("    " + "\n    ".join(tail))
        results.append(
            {
                "id": step["id"],
                "command": step["command"],
                "status": status,
                "exit_code": code,
                "duration_ms": duration_ms,
                "log_sha256": digest,
                "log_bytes": size,
                "summary": summary,
            }
        )

    if resolve(root, "HEAD") != sha or dirty_paths(root):
        raise Failure("the steps changed HEAD or the working tree; no evidence written. Fix the step and rerun.")
    passed = all(step["status"] == "passed" for step in results)
    evidence = {
        "schema": V.SCHEMA,
        "repository": V.REPOSITORY,
        "commit": sha,
        "tree": tree,
        "policy_sha256": hashlib.sha256(policy_raw).hexdigest(),
        "commit_signature": trust,
        "steps": results,
        "tools": tool_versions(policy, root, env),
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "arch": platform.machine(),
            "python": platform.python_version(),
        },
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "result": "passed" if passed else "failed",
    }
    (out / "evidence.json").write_bytes(V.canonical(evidence))
    failed = [step["id"] for step in results if step["status"] != "passed"]
    say(f"local CI {'PASSED' if passed else 'FAILED: ' + ', '.join(failed)}; evidence {out / 'evidence.json'}")
    return 0 if passed else 1


def signing_command(root: Path, folder: str, payload: Path) -> list[str]:
    """Mirror git's SSH signing: same program, same key, but our namespace."""
    program = git(root, "config", "--get", "gpg.ssh.program", check=False).stdout.decode().strip() or "ssh-keygen"
    key = git(root, "config", "--get", "user.signingkey", check=False).stdout.decode().strip()
    if not key:
        raise Failure("git config user.signingkey is not set; cannot sign evidence")
    literal = key.startswith("key::") or key.startswith(("ssh-", "ecdsa-", "sk-"))
    if literal:
        key_file = Path(folder) / "signing_key.pub"
        key_file.write_text(key.removeprefix("key::") + "\n", encoding="utf-8")
        key_path = str(key_file)
    else:
        key_path = os.path.expanduser(key)
    command = [os.path.expanduser(program), "-Y", "sign", "-n", V.NAMESPACE, "-f", key_path]
    if literal:
        command.append("-U")  # the private key lives in an agent, as git does for key:: keys
    return [*command, str(payload)]


def sign(root: Path, state_root: Path, sha: str) -> int:
    out = state_dir(state_root, sha)
    evidence_path = out / "evidence.json"
    if not evidence_path.is_file():
        raise Failure(f"no evidence for {sha}; run make ci first")
    raw = evidence_path.read_bytes()
    evidence = V.load_canonical(raw)
    if evidence.get("result") != "passed":
        raise Failure("local CI failed; refusing to sign failed evidence")
    for step in evidence.get("steps", []):
        log = out / "logs" / f"{step['id']}.log"
        if not log.is_file() or sha256_file(log) != (step["log_sha256"], step["log_bytes"]):
            raise Failure(f"log of step {step['id']} is missing or changed since the run")
    external = evidence.get("commit_signature") == "external"
    tree = git_text(root, "rev-parse", f"{sha}^{{tree}}")
    policy_raw = git(root, "cat-file", "blob", f"{sha}:{V.POLICY_PATH}").stdout
    V.validate_evidence(evidence, sha, tree, policy_raw, allow_external=external)

    with tempfile.TemporaryDirectory(prefix="klipsch-flexus-sign-") as folder:
        payload = Path(folder) / "evidence.json"
        payload.write_bytes(raw)
        command = signing_command(root, folder, payload)
        say(f"signing evidence for {sha} (namespace {V.NAMESPACE})")
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=SIGN_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise Failure(
                f"signing did not finish within {SIGN_TIMEOUT} s (a YubiKey touch or agent prompt pending?)"
            ) from None
        signature_path = Path(f"{payload}.sig")
        if result.returncode != 0 or not signature_path.is_file():
            detail = result.stderr.decode(errors="replace").strip()
            raise Failure(f"signing failed: {detail or 'exit ' + str(result.returncode)}")
        signature = signature_path.read_bytes()

    note = raw + b"\n" + signature
    try:
        # The fresh signature must pass the very checks GitHub will run.
        V.verify(root, sha, allowed_signers_text(root), allow_external=external, note=note)
    except Rejected as error:
        raise Failure(f"the fresh signature does not verify, evidence not kept: {error}") from None
    (out / "evidence.sig").write_bytes(signature)
    (out / "note").write_bytes(note)
    say(f"signed and verified; note payload {out / 'note'}")
    return 0


def pending_note(root: Path, state_root: Path, sha: str) -> tuple[bytes | None, str]:
    note = V.read_note(root, sha)
    if note is not None:
        return note, V.NOTES_REF
    path = state_dir(state_root, sha) / "note"
    if path.is_file():
        return path.read_bytes(), f"{path} (not published yet)"
    return None, "nowhere"


def verify(root: Path, state_root: Path, sha: str, *, external: bool = False) -> int:
    note, source = pending_note(root, state_root, sha)
    try:
        evidence = V.verify(root, sha, allowed_signers_text(root), allow_external=external, note=note)
    except Rejected as error:
        say(f"local CI verification FAILED: {error}")
        return 1
    say(
        f"local CI verified for {sha} from {source}: {len(evidence['steps'])} steps passed, signed {evidence['created_at']}"
    )
    return 0


def publish(root: Path, state_root: Path, sha: str, *, remote: str, dispatch: bool) -> int:
    path = state_dir(state_root, sha) / "note"
    if not path.is_file():
        raise Failure(f"no signed evidence for {sha}; run make ci first")
    note = path.read_bytes()
    external = V.parse_note(note)[2].get("commit_signature") == "external"
    allowed = allowed_signers_text(root)
    V.verify(root, sha, allowed, allow_external=external, note=note)

    # Start from what the remote already has, so the push is a fast-forward.
    remote_ref = "refs/notes/local-ci-remote"
    fetched = git(root, "fetch", "--no-tags", "--quiet", "--force", remote, f"{V.NOTES_REF}:{remote_ref}", check=False)
    if fetched.returncode == 0:
        if git(root, "rev-parse", "--verify", "--quiet", V.NOTES_REF, check=False).returncode != 0:
            git(root, "update-ref", V.NOTES_REF, remote_ref)
        else:
            git(root, "notes", "--ref", V.NOTES_REF, "merge", "--quiet", "-s", "ours", remote_ref)
    blob = git_text(root, "hash-object", "-w", "--stdin", data=note)
    git(root, "notes", "--ref", V.NOTES_REF, "add", "-f", "-C", blob, sha)
    if V.read_note(root, sha) != note:
        raise Failure("the stored note differs from the signed payload")
    V.verify(root, sha, allowed, allow_external=external)
    say(f"pushing {V.NOTES_REF} to {remote}")
    git(root, "push", "--quiet", remote, f"{V.NOTES_REF}:{V.NOTES_REF}")
    say(f"published signed local CI evidence for {sha}")
    if dispatch:
        command = ["gh", "workflow", "run", "local-ci.yaml", "--ref", "main", "-f", f"sha={sha}"]
        command += ["-f", f"external={'true' if external else 'false'}"]
        say("dispatching verification: " + " ".join(command))
        if subprocess.run(command, cwd=root, check=False).returncode != 0:
            raise Failure("gh workflow run failed; the note is published, dispatch again later")
    return 0


def machinery_changes(paths: list[str]) -> list[str]:
    """The changed paths that are not routine (PR_ROUTINE): they need CONFIRM."""
    return [
        path
        for path in paths
        if path.rsplit("/", 1)[-1] == "conftest.py" or not any(re.fullmatch(pattern, path) for pattern in PR_ROUTINE)
    ]


# Recreated in the pull request worktree from ITS requirement files, never
# linked to the owner's: PR code must not write into the venvs that later
# owner-signed runs use, and evidence must describe the PR's own pins.
PR_TOOLING = ("venv-test", "venv-testmin", "venv", "collections")


def pull_request(root: Path, number: int, *, remote: str, confirm: bool) -> int:
    """Test someone else's PR head with THIS runner; its steps still run the PR's code."""
    sha = (
        subprocess.run(
            ["gh", "pr", "view", str(number), "--json", "headRefOid", "-q", ".headRefOid"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    if not V.SHA_RE.fullmatch(sha):
        raise Failure(f"cannot resolve the head of PR #{number}")
    git(root, "fetch", "--no-tags", "--quiet", remote, "main")
    git(root, "fetch", "--no-tags", "--quiet", remote, f"pull/{number}/head")
    if resolve(root, "FETCH_HEAD") != sha:
        raise Failure(f"PR #{number} moved while fetching; retry")
    base = git_text(root, "merge-base", f"{remote}/main", sha)
    changed = [line for line in git_text(root, "diff", "--name-only", "--no-renames", base, sha).splitlines() if line]
    say(f"PR #{number} head {sha} changes {len(changed)} file(s):\n  " + "\n  ".join(changed))
    machinery = machinery_changes(changed)
    if machinery and not confirm:
        raise Failure(
            f"PR #{number} changes files that can alter what the CI steps do:\n  "
            + "\n  ".join(machinery)
            + "\nreview them, then rerun with CONFIRM=1"
        )
    say(
        f"PR #{number}: its code (tests, integration, and with CONFIRM its Makefile and tooling) runs on this "
        "Mac as you, with a scrubbed environment but your files and keys within reach; review the diff first"
    )
    worktree = Path(tempfile.mkdtemp(prefix=f"klipsch-flexus-pr{number}-"))
    worktree.rmdir()
    git(root, "worktree", "add", "--detach", "--quiet", str(worktree), sha)
    try:
        command = ["make", *PR_TOOLING]
        say(f"building the PR's own tooling: {' '.join(command)}")
        if subprocess.run(command, cwd=worktree, env=step_env(sha), stdin=subprocess.DEVNULL, check=False).returncode:
            raise Failure(f"{' '.join(command)} failed in {worktree}")
        code = run(worktree, root, external=True)
        if code != 0:
            return code
        sign(root, root, sha)
        return publish(root, root, sha, remote=remote, dispatch=True)
    finally:
        git(root, "worktree", "remove", "--force", str(worktree), check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", help="repository checkout (default: the one containing the current directory)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="run every policy step on the clean HEAD and write evidence")
    for name in ("sign", "verify", "publish"):
        sub = commands.add_parser(name)
        sub.add_argument("--sha", default="HEAD", help="commit (default HEAD)")
        if name == "verify":
            sub.add_argument("--allow-external", action="store_true", help="accept evidence for a non-owner PR head")
        if name == "publish":
            sub.add_argument("--remote", default="origin")
            sub.add_argument("--dispatch", action="store_true", help="also run the GitHub verify workflow for it")
    pr = commands.add_parser("pr", help="run, sign, publish and dispatch verification for a pull request head")
    pr.add_argument("--number", type=int, required=True)
    pr.add_argument("--remote", default="origin")
    pr.add_argument(
        "--confirm", action="store_true", help="the PR changes files outside PR_ROUTINE and you reviewed them"
    )
    args = parser.parse_args(argv)

    try:
        root = toplevel(args.root)
        if args.command == "run":
            return run(root, root)
        if args.command == "pr":
            return pull_request(root, args.number, remote=args.remote, confirm=args.confirm)
        sha = resolve(root, args.sha)
        if args.command == "sign":
            return sign(root, root, sha)
        if args.command == "verify":
            return verify(root, root, sha, external=args.allow_external)
        return publish(root, root, sha, remote=args.remote, dispatch=args.dispatch)
    except (Failure, Rejected) as error:
        say(f"local CI: {error}")
        return 2
    except subprocess.CalledProcessError as error:
        say(f"local CI: {error.cmd[0]} failed (exit {error.returncode})")
        return 2


if __name__ == "__main__":
    sys.exit(main())
