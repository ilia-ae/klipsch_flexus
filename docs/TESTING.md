# Testing

The integration is distributed only through HACS: you install and update it from a
GitHub release. Nothing in this repository deploys to a Home Assistant instance.
Everything below runs on a developer machine, or on throwaway containers.

## Quick start

```bash
make venv-test venv-testmin   # once: Python 3.14 + current HA, Python 3.12 + oldest supported HA (uv)
make test                     # pytest on both Home Assistant versions
make ruff                     # ruff check + format --check (ruff 0.17.2 via uvx)
make help                     # every target
```

| Venv | Python | Requirements | Home Assistant |
| --- | --- | --- | --- |
| `.venv-test` | 3.14 | `requirements_test.txt` (Dependabot bumps it) | the pinned current release |
| `.venv-testmin` | 3.12 | `.github/ci/requirements_test_min.txt` | 2024.11.0, the oldest in `hacs.json` |

## Local CI and signed evidence

All CI runs locally on the owner's Mac. GitHub runs no tests. It only checks that
the owner signed evidence of a passing local run for the exact commit.

### What `make ci` does

`make ci` runs `scripts/local_ci.py run` and then `scripts/local_ci.py sign`.
Both scripts use only the Python standard library and run with `python3 -I`.

1. **Refuse unclean input.** The run stops if a tracked file has changed anywhere,
   or if an untracked file sits under `custom_components/`, `tests/`, `ansible/`,
   `.ci/`, `scripts/`, `tools/`, `mk/` or `.github/` (or is `Makefile`,
   `pyproject.toml`, `requirements_test.txt` or `hacs.json`). It also stops if
   `HEAD` is not signed by an allowed signer for `code@ilia.ae` (`git commit -S`).
2. **Run every step** of [`.ci/local-ci.json`](../.ci/local-ci.json) as it is at
   `HEAD`, in order. A failing step does not stop the run. Each step's log goes to
   `.local-ci/<sha>/logs/<step>.log` (gitignored).

   | Step | Command | What it checks |
   | --- | --- | --- |
   | `ruff` | `make ruff` | lint and formatting |
   | `lint-workflows` | `make lint-workflows` | actionlint (with shellcheck) and yamllint on `.github/` |
   | `local-ci-selftest` | `make ci-selftest` | the runner and the verifier, using throwaway keys |
   | `pytest-latest` | `make test-latest` | the test suite on the current Home Assistant |
   | `pytest-min` | `make test-min` | the test suite on the oldest supported Home Assistant |
   | `hassfest` | `make hassfest` | the official hassfest container (pinned by digest) on the tracked integration files |
   | `lint-ansible` | `make lint-ansible` | yamllint and ansible-lint on `ansible/` |
   | `molecule` | `make molecule-scenarios SCENARIOS=...` | the install role on throwaway `klipsch-flexus-*` containers, one scenario at a time |

3. **Discard a run that changed the tree.** If a step changed `HEAD` or the
   working tree, the run writes no evidence.
4. **Write the evidence** to `.local-ci/<sha>/evidence.json` as canonical JSON:
   sorted keys, no whitespace, ASCII only, no floats. It records:
   - schema `klipsch-flexus-local-ci/1` and repository `ilia-ae/klipsch_flexus`
   - the commit SHA, its tree SHA, and the SHA-256 of the policy blob
   - for each step: its id, command, status, exit code, duration, and the
     SHA-256 and size of its log
   - tool versions: ruff, Python and Home Assistant in both venvs, the hassfest
     image digest and local image ID, Docker, ansible-core and Molecule
   - the host OS, release, architecture and Python version
   - `created_at` and the overall result
5. **Sign.** `sign` refuses failed evidence, and evidence whose logs changed after
   the run. It signs the evidence with exactly the key and program git signs
   commits with (`user.signingkey` and `gpg.ssh.program`, so on the owner's Mac
   that is `git-sign-helper` with the YubiKey-backed agent). The signing command
   is `ssh-keygen -Y sign` in the dedicated namespace
   **`klipsch-flexus-local-ci@ilia.ae`**. Git commit and tag signatures use the
   namespace `git`, so they can never be replayed as CI evidence, and evidence
   signatures can never pass as commit signatures. The fresh signature is checked
   against your allowed signers by the same verifier GitHub runs. Only then is it
   kept, as `.local-ci/<sha>/note`: the evidence line followed by the armored
   signature.

### Publishing and verification

```bash
git commit -S ...      # every commit on main is signed (commit.gpgsign=true)
make ci                # run + sign (Molecule included: takes a while)
make ci-publish        # adds the note to refs/notes/local-ci and pushes ONLY that ref
git push origin main   # GitHub verifies; order does not matter (it waits ~3 min for the note)
make ci-verify         # optional: the remote checks, locally
```

`make ci-publish` merges the remote `refs/notes/local-ci`, stores the note for the
commit, verifies it again and pushes only `refs/notes/local-ci`. Use
`make ci-publish DISPATCH=1` to also start the verify workflow for a commit that
is not on `main` (`gh workflow run local-ci.yaml -f sha=<sha>`).

The workflow [**Verify signed local CI**](../.github/workflows/local-ci.yaml) runs
on pushes to `main` and `v*` tags, on pull requests, and on `workflow_dispatch`
(input `sha`). It never runs project code. From the workflow's own revision
(`github.workflow_sha`) it does the following:

1. Runs `python3 -I scripts/test_local_ci.py`, so the verifier proves it still
   rejects forged, stale and incomplete evidence.
2. Fetches the commit and `refs/notes/local-ci`, retrying for up to 3 minutes.
3. Runs `scripts/verify_local_ci.py`. It reads the commit, its tree and its
   `.ci/local-ci.json` as git data only, and checks these points:
   - The commit is signed (`git verify-commit`) by a key listed for
     `code@ilia.ae` in the repository variable `LOCAL_CI_ALLOWED_SIGNERS`.
   - A note exists for the commit. It must hold exactly one canonical JSON line
     and one SSH signature, and nothing else.
   - The signature passes `ssh-keygen -Y verify -I code@ilia.ae -n
     klipsch-flexus-local-ci@ilia.ae` against the same allowed signers.
   - The evidence has the right schema and repository, `commit == sha`, and
     `tree == sha^{tree}`.
   - The policy digest matches the policy blob at that commit.
   - Every step that policy requires is present, in order, with the same
     command, `passed` and exit code 0. The overall result is `passed`.
   - The evidence has no unknown fields, duplicate keys or floats.

A missing note fails with:
`no signed local CI evidence for <sha>: run make ci && make ci-publish`.

A dispatch on `main` also sets the commit status **`local-ci/verified`** on the
target commit, in a separate job with `statuses: write`. Every other job has
`contents: read` only.

### Trust model

- **Root of trust**: the repository variable `LOCAL_CI_ALLOWED_SIGNERS`. It holds
  allowed-signers lines in the format of `~/.ssh/allowed_signers`, for example
  `code@ilia.ae ecdsa-sha2-nistp256 AAAA...`. Each line must either have no
  `namespaces=` option, or list both `git` and `klipsch-flexus-local-ci@ilia.ae`.
  The repository content does not change this trust root.
- **Push to `main` and tags**: the workflow file comes from the pushed commit,
  and only the owner can push. The verifier also requires that commit to be
  owner-signed.
- **Pull requests**: GitHub takes the workflow file and the verifier from the PR
  merge commit. For a fork PR, that is the contributor's code. The PR check is
  therefore advisory: it has a read-only token and no secrets. The authoritative
  result is a dispatch on `main`, which runs the verifier from `main`
  (`github.workflow_sha`) and sets `local-ci/verified`. A dispatch from any
  other ref is skipped.
- **Releases** ([release.yaml](../.github/workflows/release.yaml)): the workflow
  checks that the tag equals the `manifest.json` version. It runs the same
  verifier for the tag's commit, and also requires the tag to be an annotated
  tag signed by an allowed signer (`git verify-tag`). Only then does
  `softprops/action-gh-release` publish the release that HACS installs.

One-time setup for the owner: put the allowed signers in the repository variable
`LOCAL_CI_ALLOWED_SIGNERS`, for example with
`gh variable set LOCAL_CI_ALLOWED_SIGNERS < ~/.ssh/allowed_signers`. Then make
**Verify signed local CI** a required check for `main`.

### Releases

```bash
# bump custom_components/klipsch_flexus/manifest.json "version", commit -S
make ci
make release-tag VERSION=x.y.z    # checks manifest version + local evidence, then git tag -s vx.y.z
make ci-publish
git push origin main vx.y.z
```

### Pull requests and Dependabot

Pull request commits are not owner-signed and carry no evidence, so
**Verify signed local CI** fails on them at first. That is expected. After
reviewing the PR:

```bash
make ci-pr PR=<number>             # CONFIRM=1 if the PR touches .ci/, scripts/, Makefile, mk/ or .github/
```

`ci-pr` uses the runner from your trusted checkout. It works in these steps:

1. Fetches `pull/<n>/head` and checks the head is the commit GitHub reports.
2. Checks it out in a temporary worktree. Your `.venv*` and
   `ansible/collections` are symlinked into it.
3. Runs the PR's policy there. **This executes the PR's code (its tests and
   Makefile) on your Mac, so review the diff first.**
4. Signs the evidence, marked `commit_signature: external`, and publishes the
   note.
5. Dispatches verification with `external=true`. That sets `local-ci/verified`
   on the PR head.

External evidence is accepted only for a commit that is not on `main`. Pushes to
`main` and tags always need an owner-signed commit. So merge pull requests
locally with a signed commit, for example
`git merge --no-ff -S` or `git merge --squash` followed by `git commit -S`. Then
run `make ci && make ci-publish` and push. GitHub's merge button creates a commit
signed by GitHub, not by the owner, and that commit fails verification on `main`.

### HACS validation (not part of the signed policy)

The HACS action (`ghcr.io/hacs/action`) fetches everything through the GitHub
API: repository description, topics, issues, archived flag, releases, and the
files at a ref that has already been pushed. It never reads the local checkout.
It cannot attest an unpushed commit, and its result depends on repository
settings rather than on the commit. So it is listed under `not_required` in the
policy. Run it after pushing and before a release:

```bash
make hacs REF=main                          # or REF=vX.Y.Z / a pushed SHA; anonymous GitHub API
HACS_TOKEN="$(gh auth token)" make hacs     # only if anonymous requests are rate-limited
```

### Pinned images

Both `hassfest` and `hacs` run official images pinned by multi-arch index digest
in the `Makefile`. They publish `linux/amd64` only, so Docker Desktop on Apple
Silicon runs them under emulation. The containers are named
`klipsch-flexus-hassfest-*` and `klipsch-flexus-hacs-*` and removed on exit. To
move a pin, use this command, then update the `Makefile` and commit:

```bash
docker buildx imagetools inspect ghcr.io/home-assistant/hassfest:latest   # take the index Digest
```

### Troubleshooting

| Message | Meaning |
| --- | --- |
| `refusing to run on a dirty tree` | commit or stash first; `.local-ci/` and `.venv*` are ignored |
| `HEAD ... is not signed by an allowed signer` | amend with `git commit --amend -S --no-edit`, or use `make ci-pr` for someone else's PR |
| `signing did not finish within 60 s` | the signing agent is waiting for a YubiKey touch or is not running |
| `no signed local CI evidence for <sha>` | the note was never published: `make ci && make ci-publish` |
| `stale evidence` | the note belongs to another commit or tree: rerun `make ci` on this commit |
| `lacks required step(s)` | the policy at this commit requires a step the evidence does not have |
