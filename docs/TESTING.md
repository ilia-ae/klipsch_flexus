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

## Molecule (HACS-like install/upgrade on real HA)

The pytest suites (`tests/`) test the integration against Home Assistant's test harness. The
Molecule scenarios add what those cannot see: the integration installed into the **official Home
Assistant container image** the way HACS installs it, Home Assistant restarted, the soundbar added
through the real config flow, and the result checked through Home Assistant's own REST and
WebSocket APIs.

Everything here is test-only. The only hosts are throwaway `klipsch-flexus-*` containers on an
internal Docker network (no route to the internet or the LAN). The "soundbar" is a fake device
inside the same container. Nothing in this repository deploys to a real Home Assistant: users and
the owner install and update the integration through HACS.

### Run

From the repository root (GNU make 3.81 or newer, Docker, Python 3.13 at
`/opt/homebrew/bin/python3.13`, or set `ANSIBLE_PYTHON`):

```sh
make venv collections lint-ansible
make molecule-scenarios SCENARIOS="klipsch_flexus_install/fresh klipsch_flexus_install/upgrade klipsch_flexus_install/minimum"
make molecule-list                                           # every scenario
```

`make venv` creates `.venv` from `requirements-dev.txt` (pinned ansible-core, ansible-lint,
molecule, molecule-plugins[docker], yamllint). `make collections` installs the pinned collections
of `ansible/requirements.yml` into `ansible/collections`. Both compare what is installed with the
committed pins (`scripts/check_pins.py`), not file times, and reinstall only on a difference.
Both directories are gitignored; in a git worktree run both targets there (or symlink them from
the main checkout, never commit the links).

`molecule-scenarios` runs one full `molecule test` per scenario (create, prepare, converge,
idempotence, verify, destroy), one at a time because the Docker VM is shared, and prints a summary.
It exits non-zero when any scenario failed. Each scenario takes about 2 to 3 minutes on an Apple
Silicon Mac.

Inner loop on a kept container:

```sh
make molecule-scenarios SCENARIOS=klipsch_flexus_install/fresh MOLECULE_ARGS=--destroy=never
make molecule-stage STAGE=converge S=klipsch_flexus_install/fresh   # also: create prepare idempotence verify destroy
make molecule-cleanup SCENARIOS=klipsch_flexus_install/fresh        # no SCENARIOS = every scenario
```

`molecule-cleanup` removes only the scenario's own `klipsch-flexus-*` container and network and
its `.molecule/<role>/<scenario>` state, never another container. If Docker Desktop restarts
under a run ("unexpected EOF", "docker.sock ... no such file"), that is infrastructure, not a test
result: `scripts/molecule.sh` waits until `docker info` answers and reruns that scenario once.

### Pieces

| Path | What it is |
|---|---|
| `ansible/roles/klipsch_flexus_install` | Installs `custom_components/klipsch_flexus` like HACS: a full replace of `/config/custom_components/klipsch_flexus` from a source tree on the controller (this checkout, or an older release from `git archive`), compared by content (files that Home Assistant compiles into `__pycache__` are ignored). Only when something changed it restarts Home Assistant through the image's s6 supervisor (`s6-svc -h`: SIGHUP is Home Assistant's "restart", exit code 100 keeps the container up) and waits until the new process answers. A second run reports `changed=0` and does not restart. |
| `ansible/roles/flexus_stub` | A fake Klipsch Flexus (Python stdlib) supervised by s6 next to Home Assistant, on loopback `127.0.0.2` (ports 80 and 8008). It serves `getData` (value and edit roles), `getRows` (`dirac:filters`), `setData` (POST, `authMode` `none`; the legacy GET answers 405 like 2026 firmware) and `eureka_info` from the non-secret `files/fixture.json` (MAC `02:00:00:00:00:01`, a locally administered documentation address; `eureka_info` reports the all-zero MAC as 2026 firmware does). Every write is recorded in `/var/lib/flexus-stub/writes.jsonl`; a read of a path the fixture does not know answers 404 and is recorded in `unknown_paths.jsonl`. Not emulated: the 2026 firmware's write authentication (see below). |
| `ansible/molecule/resources` | Shared playbook tasks, variables and `ha_api.py`, a small REST/WebSocket client that runs inside the container with the image's Python: onboarding of a test owner (`/api/onboarding/users` -> auth code -> `/auth/token` -> long-lived token), REST and WebSocket calls, image hashes. |
| `scripts/molecule.sh`, `mk/ansible.mk` | The runner behind the make targets (sequential runs, summary, cleanup, Docker-restart rerun). |

Home Assistant images are pinned by their multi-arch index digest (linux/amd64 and linux/arm64);
Docker runs the host's architecture natively, so every scenario runs natively on an Apple Silicon Mac and
on an amd64 host alike. They are the `molecule` step of the local CI below.

### What each scenario proves

**Not covered: the 2026 firmware's signed writes.** Real 2026 firmware reports `authMode`
`setData` and answers 401 to every unsigned write except volume and mute; the integration then
resolves the device MAC (`primaryMacAddress`, then the registry) and retries with an
`HMAC_SHA256_AES256`-signed POST over HTTPS. The stub reports `authMode` `none`, has no HTTPS
endpoint and accepts every unsigned write, so the integration never takes that path here, and the
"writes reach the stub" checks below would still pass if signed writes were broken. That path is
covered only by the pytest suite (`tests/test_auth.py` known answers, the 401/oracle/signed-retry
tests in `tests/test_api.py`), against mocked HTTP.

**`klipsch_flexus_install/fresh`** (Home Assistant 2026.10.4): a new HACS user.

- The role installs this checkout and restarts Home Assistant; the second run changes nothing and
  does not restart (idempotence).
- Home Assistant loaded the checkout's version (WebSocket `manifest/get`) and logged that it found
  the custom integration.
- The config flow's user step (host `127.0.0.2`) creates an entry titled from `eureka_info`
  that reaches state `loaded`, and its unique_id is the device's primary MAC (`020000000001`),
  not the host (read from `.storage/core.config_entries`: no API exposes a config entry's
  unique_id).
- Every expected entity exists (media player, the six selects including `6. Idle Timeout`, the
  thirteen numbers, the sensors and switches) and none is the old idle-timeout number. Their
  states come from the stub: media player `playing` at volume 0.4 (20 of the 0..50 range read
  from the `edit` metadata), source `TV ARC`, sound mode, title and artist; idle timeout
  `10_min` (600 s), EQ preset `custom`, Dirac filter `Living Room` (from `getRows`), tone and
  channel levels, balance, switches, the device-status sensor and a delay sensor.
- Setting up the integration wrote nothing to the device. `media_player.volume_set` 0.3 and
  `select.select_option` `15_min` reach the stub as exactly two writes (`player:volume` i32 15,
  `settings:/system/maxIdleTime` i32 900), and the entities show the values read back.
- The integration read no path the stub does not emulate.
- `GET /api/brands/integration/klipsch_flexus/{icon,icon@2x,dark_icon,dark_icon@2x}.png` answer 200
  with the exact bytes of `custom_components/klipsch_flexus/brand/` (Home Assistant 2026.3+
  serves an integration's own brand images before the CDN: the dark-theme logo fix).
- No `ERROR`/`CRITICAL` line mentioning `klipsch_flexus` and no traceback frame in
  `custom_components/klipsch_flexus/` in the container log (`docker logs`: every Home Assistant
  run of the container), no such error in Home Assistant's system log, and no warning at all from
  the integration's own loggers.

**`klipsch_flexus_install/upgrade`** (Home Assistant 2026.10.4): what a HACS user experiences on
update.

- prepare: release v2.5.17, extracted from this repository with `git archive v2.5.17` (no network;
  the tag must be in the clone), is installed with the same role and Home Assistant restarted; the
  soundbar is added through the config flow. Recorded in the container: the entry, its unique_id
  (v2.5.17 keys it by host because `eureka_info` reports the all-zero MAC), the entity registry
  (it has `number.*_idle_timeout`) and the number of writes so far.
- converge: this checkout replaces v2.5.17 like a HACS update, then a restart; idempotence as above.
- verify: the same entry is still the only one and `loaded`, now keyed by the stub's MAC; a second
  config flow for the same soundbar under another address (`127.0.0.3`) aborts with
  `already_configured`. The number idle timeout is gone from the registry and from the states, the
  select `6. Idle Timeout` exists with the stub's value, and every other entity kept its entity_id
  (dashboards and automations keep working). All entity states as in `fresh`, the update wrote
  nothing to the device, brand images byte for byte, and the logs of both releases are clean.

**`klipsch_flexus_install/minimum`** (Home Assistant 2024.11.0, the oldest supported release, as in
`.github/ci/requirements_test_min.txt`): fresh install and restart, config flow to `loaded` with
the MAC unique_id, the same entities, states and two writes as `fresh`, and clean logs. No
brand-image check: Home Assistant before 2026.3 has no local brands.

## Local CI and signed evidence

All CI runs locally on the owner's Mac. GitHub runs no tests. It only checks that
the owner signed evidence of a passing local run for the exact commit.

### What `make ci` does

`make ci` runs `scripts/local_ci.py run` and then `scripts/local_ci.py sign`.
Both scripts use only the Python standard library and run with `python3 -I`.

1. **Refuse unclean input.** The run stops if a tracked file has changed, if any
   untracked file exists anywhere, or if an ignored file exists other than local
   tooling and caches (`.venv*`, `ansible/collections`, `.local-ci/`,
   `.molecule/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, `.DS_Store`,
   `.coverage`, `.claude/`, `.reverse/`; `IGNORED_OK` in `scripts/local_ci.py`).
   A stray `GNUmakefile`, `pytest.ini`, `conftest.py` or `ruff.toml` would change
   what the steps do without changing the commit. It also stops if `HEAD` is not
   signed by an allowed signer for `code@ilia.ae` (`git commit -S`).
2. **Run every step** of [`.ci/local-ci.json`](../.ci/local-ci.json) as it is at
   `HEAD`, in order. A failing step does not stop the run. Each step's log goes to
   `.local-ci/<sha>/logs/<step>.log` (gitignored). Steps get an allow-listed
   environment (`PATH`, `HOME`, `USER`, `TMPDIR`, locale, Docker and proxy
   settings; `STEP_ENV` in `scripts/local_ci.py`), so `make ci UVX=true` (via
   `MAKEFLAGS`), a leftover `MOLECULE_ARGS`, `IMAGES` or `PYTHON`, tokens and
   `SSH_AUTH_SOCK` never reach a step. The pytest steps first check that their venv
   has exactly what the committed requirements file pins (`scripts/check_pins.py`);
   after a Dependabot bump they fail with `stale .venv-test: run make venv-test`
   instead of testing, and signing, the previous Home Assistant.

   A step may declare a `summary` in the policy: `pattern`, a regular
   expression that the runner applies to the step's log (multiline), and an
   optional `format` with `$name` groups of that pattern (default: the whole
   match). Each match gives one part; the parts are joined with `, `. The result
   must be at most 120 plain characters (letters, digits, space and
   `.,:;/()+%=_-`), otherwise the step has no summary. The runner prints it next
   to the step's status. Declared today:

   | Step | Summary, for example |
   | --- | --- |
   | `local-ci-selftest` | `72 tests` |
   | `pytest-latest`, `pytest-min` | `183 passed` (also skipped and warning counts, when there are any) |
   | `hassfest` | `ok` (only when hassfest reports `Invalid integrations: 0`) |
   | `molecule` | `fresh, upgrade, minimum` (a failed scenario shows as `FAIL <name>`) |

   | Step | Command | What it checks |
   | --- | --- | --- |
   | `ruff` | `make ruff` | lint and formatting |
   | `lint-workflows` | `make lint-workflows` | actionlint and shellcheck on the workflows and `scripts/*.sh`, yamllint on `.github/` |
   | `local-ci-selftest` | `make ci-selftest` | the runner and the verifier, using throwaway keys |
   | `pytest-latest` | `make test-latest` | the test suite on the current Home Assistant |
   | `pytest-min` | `make test-min` | the test suite on the oldest supported Home Assistant |
   | `hassfest` | `make hassfest` | the official hassfest image (pinned by digest, or its native rebuild, see below) on the tracked integration files |
   | `lint-ansible` | `make lint-ansible` | yamllint and ansible-lint on `ansible/` |
   | `molecule` | `make molecule-scenarios SCENARIOS=...` | the install role on throwaway `klipsch-flexus-*` containers, one scenario at a time |

3. **Discard a run that changed the tree.** If a step changed `HEAD` or the
   working tree, the run writes no evidence.
4. **Write the evidence** to `.local-ci/<sha>/evidence.json` as canonical JSON:
   sorted keys, no whitespace, ASCII only, no floats. It records:
   - schema `klipsch-flexus-local-ci/2` and repository `ilia-ae/klipsch_flexus`
   - the commit SHA, its tree SHA, and the SHA-256 of the policy blob
   - for each step: its id, command, status, exit code, duration, the
     SHA-256 and size of its log, and its summary (`null` when there is none)
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
   - A step's summary is `null`, or a plain string of at most 120 characters
     from the charset above, and only for a step whose policy declares a
     `summary`.
   - The evidence has no unknown fields, duplicate keys or floats.

A missing note fails with:
`no signed local CI evidence for <sha>: run make ci && make ci-publish`.

A dispatch on `main` also sets the commit status **`local-ci/verified`** on the
target commit, in a separate job with `statuses: write`. A push to `main` also
updates the [test-result badges](#test-result-badges), in a separate job with
`contents: write`. Every other job has `contents: read` only.

### Test-result badges

The section **Test results** of the [README](../README.md#test-results) shows
shields.io badges for pytest (both Home Assistant versions), hassfest, Molecule
and the signature. They come from the signed evidence of the latest commit on
`main`, never from a person typing them.

After a push to `main`, and only when the job **Verify signed local CI**
succeeded, the job **Publish test-result badges (ci-results)** runs. It is the
only job with `contents: write`. It works like this:

1. It runs `scripts/verify_local_ci.py --write-badges <dir>` from the pushed
   commit. The verifier checks the note again. Then `badge_files` builds every
   file from that verified note with `json.dumps`. No evidence text passes
   through the shell.
2. It skips the update when `main` has moved on to a newer commit. The run for
   that commit updates the branch instead.
3. It stores the files as one new commit without a parent on the orphan
   branch **`ci-results`**, and force-pushes it with a lease on the commit it
   read. So the branch always has exactly one commit, written by
   `github-actions[bot]` (not signed).

| File on `ci-results` | Content |
| --- | --- |
| `badges/pytest-latest.json`, `badges/pytest-min.json` | `HA 2026.10 · 183 passed`: the Home Assistant version from the evidence tools, and the step summary |
| `badges/hassfest.json` | `ok` |
| `badges/molecule.json` | `fresh · upgrade · minimum` |
| `badges/signed.json` | `signed · <short sha> · <date of the run>` |
| `evidence/latest.json`, `evidence/latest.json.sig` | the evidence of the newest commit (the exact signed bytes) and its SSH signature |
| `evidence/<sha>.json`, `evidence/<sha>.json.sig` | the same for each commit; kept from update to update |
| `allowed_signers` | the trust root the workflow verified with (`LOCAL_CI_ALLOWED_SIGNERS`) |

A badge without a summary in the evidence shows `passed`. A step that is not in
the evidence gets no badge file.

To check the evidence yourself, see the README. To check only a signature:

```bash
ssh-keygen -Y verify -f allowed_signers -I code@ilia.ae -n klipsch-flexus-local-ci@ilia.ae \
  -s evidence/latest.json.sig < evidence/latest.json
```

That proves who signed the evidence. `scripts/verify_local_ci.py` also proves
that it belongs to the commit, its tree and its policy. Compare
`allowed_signers` with the owner's SSH signing keys on GitHub
(`https://api.github.com/users/ilia-ae/ssh_signing_keys`).

If a ruleset or branch protection covers every branch, allow the workflow to
force-push `ci-results`, or the job fails.

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
  merge commit, so the PR controls that run (it could simply `exit 0`). It is
  therefore named **Verify signed local CI (advisory)** and means nothing on its
  own; it has a read-only token and no secrets. The authoritative result is a
  dispatch on `main`, which runs the verifier from `main` (`github.workflow_sha`)
  and sets the commit status `local-ci/verified` on the PR head. A dispatch from
  any other ref is skipped. Fork PR tokens cannot write commit statuses.
- **Releases** ([release.yaml](../.github/workflows/release.yaml)): the workflow
  accepts only tags `vX.Y.Z` and `vX.Y.Z-beta.N`, and checks that the tag equals
  `v` plus the `manifest.json` version. It runs the same
  verifier for the tag's commit, and also requires the tag to be an annotated
  tag signed by an allowed signer (`git verify-tag`). Only then does
  `softprops/action-gh-release` publish the release that HACS installs.

One-time setup for the owner: put the allowed signers in the repository variable
`LOCAL_CI_ALLOWED_SIGNERS`, for example with
`gh variable set LOCAL_CI_ALLOWED_SIGNERS < ~/.ssh/allowed_signers`. If you
protect `main` with required checks, require the commit status
**`local-ci/verified`** with **GitHub Actions** as its expected source. Do not
require the job **Verify signed local CI**: on a pull request the only check run
with a matching name would come from the PR's own workflow file. The owner's
signed pushes to `main` are verified by the push run of the same workflow.

### Releases

User-facing changes ship first as a beta. A stable release follows only on the
owner's word.

| Tag | `manifest.json` version | GitHub release | Who gets it in HACS |
| --- | --- | --- | --- |
| `vX.Y.Z-beta.N` | `X.Y.Z-beta.N` | pre-release, never marked Latest | only users who enable **Show beta versions** for this repository |
| `vX.Y.Z` | `X.Y.Z` | normal release, marked Latest | everyone |

Any other tag (`v1.2`, `v1.2.3-rc1`, `v1.2.3b1`) is refused by the release
workflow. Both forms are valid versions for Home Assistant and hassfest:
AwesomeVersion reads `X.Y.Z-beta.N` as SemVer, and it sorts before `X.Y.Z`.
Release notes are generated by GitHub, as before.

```bash
git fetch --tags origin
make release-beta-next BASE=x.y.z  # prints the next free beta, e.g. x.y.z-beta.1 (local tags only)
# set custom_components/klipsch_flexus/manifest.json "version" to it, commit -S
make ci
make release-tag VERSION=x.y.z-beta.n   # checks the format, the manifest version and the local evidence, then git tag -s
make ci-publish
git push origin main vx.y.z-beta.n
```

For the stable release, set the version to `x.y.z`, commit, and run the same
steps with `VERSION=x.y.z`. Without `BASE`, `release-beta-next` uses the
`x.y.z` part of the manifest version.

### Pull requests and Dependabot

Pull request commits are not owner-signed and carry no evidence, so
**Verify signed local CI (advisory)** fails on them at first. That is expected,
and that run is advisory anyway; `local-ci/verified` is what counts. Dependabot
PRs change requirement files or `.github/`, so they always need `CONFIRM=1`
after you have read the bump. After reviewing the PR:

```bash
make ci-pr PR=<number>             # CONFIRM=1 if it changes anything beyond integration code, tests/test_*.py and docs
```

`ci-pr` uses the runner from your trusted checkout. It works in these steps:

1. Fetches `pull/<n>/head` and checks the head is the commit GitHub reports.
2. Lists every changed file. Unless all of them are routine (`PR_ROUTINE` in
   `scripts/local_ci.py`: `custom_components/klipsch_flexus/` code, JSON,
   translations and brand images, `tests/test_*.py`, `README.md` and `docs/`),
   it stops and asks for `CONFIRM=1`. Any `conftest.py`, makefile, `mk/`,
   `pyproject.toml`, requirements file, lint configuration, `.ci/`, `scripts/`,
   `ansible/` or `.github/` change, and any new top-level file, can change what
   the steps do, so review those files before confirming.
3. Checks it out in a temporary worktree and builds the PR's own tooling there
   from its requirement files (`make venv-test venv-testmin venv collections`).
   Nothing is linked to your venvs, so PR code cannot write into the tooling that
   later owner-signed runs use.
4. Runs the PR's policy there, with the same allow-listed environment as
   `make ci` (no tokens, no `SSH_AUTH_SOCK`).
5. Signs the evidence, marked `commit_signature: external`, and publishes the
   note.
6. Dispatches verification with `external=true`. That sets `local-ci/verified`
   on the PR head.

**`ci-pr` is not a sandbox.** The PR's tests, integration code and (with
`CONFIRM=1`) Makefile run on your Mac as your user. They can read and write
your files (the main checkout, `~/.ssh`, the `gh` keychain entry) and reach the
signing agent: `git-sign-helper` signs through a socket at a fixed path, not
through `SSH_AUTH_SOCK`, so code running as you could ask it to sign evidence or
commits. Run `ci-pr` only for a PR whose full diff you have read, the same as
running its code by hand.

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
policy.

HACS asks every repository in its default list (this one is) to run it as a
GitHub Action. [`validate.yaml`](../.github/workflows/validate.yaml) does that
on pushes to `main` and `v*` tags, daily and on demand. It checks out nothing
and runs no repository code: it runs the HACS image pinned by the same digest
as the `Makefile` (`HACS_IMAGE`) against the pushed commit with a read-only
token. That is verification of pushed state, which fits "GitHub only verifies".

hassfest, the other action HACS lists for integrations, runs only locally (the
`hassfest` step, the pinned official image, recorded in the signed evidence).
That deviates from the letter of HACS's inclusion checklist; if HACS reviewers
ask for a hassfest workflow, restore one.

To run the HACS validation by hand, after pushing:

```bash
make hacs REF=main          # or REF=vX.Y.Z / a pushed SHA
```

The action needs a GitHub token: with an empty token, the API answers HTTP 401.
`make hacs` uses `HACS_TOKEN` when it is set, and otherwise reads
`gh auth token` at run time. It passes the token to the container through the
environment, never on the command line, and never writes it to a file. The
`gh` token usually carries broad scopes, so a fine-grained token with read-only
access to public repositories is the better `HACS_TOKEN`.

### Pinned images

The `Makefile` pins each official image by its multi-arch index digest. It also
records the upstream commit and Dockerfile the image was built from, taken from
the image's build provenance:

| Target | Official image | Built from |
| --- | --- | --- |
| `hassfest` | `ghcr.io/home-assistant/hassfest@sha256:f9ac52cf…` | `home-assistant/core` `74cf5a49…`, `script/hassfest/docker/Dockerfile` |
| `hacs` | `ghcr.io/hacs/action@sha256:187499a0…` | `hacs/integration` `0704ffc6…`, `action/Dockerfile` |

Both images publish `linux/amd64` only. The script `scripts/pinned_image.sh`
picks which image to run:

- On a Docker engine that runs amd64 natively, it uses the official image.
- Anywhere else, it builds that Dockerfile once at that commit for the native
  architecture, as `klipsch-flexus-hassfest:<commit>` or
  `klipsch-flexus-hacs:<commit>`. This covers Docker Desktop on Apple Silicon
  without Rosetta emulation, where the official image fails with
  `exec format error`.

Set `IMAGES=official` or `IMAGES=local` to override the choice. The evidence
records the image reference and its local image ID (`make -s hassfest-image`).
Containers are named `klipsch-flexus-hassfest-*` and `klipsch-flexus-hacs-*` and
are removed on exit.

To move a pin, update the digest and the provenance commit in the `Makefile`
together:

```bash
docker buildx imagetools inspect ghcr.io/home-assistant/hassfest:latest            # index Digest
docker buildx imagetools inspect --format '{{json .Provenance}}' ghcr.io/home-assistant/hassfest@sha256:<digest> | grep -o '"revision": *"[0-9a-f]*"'
```

### Troubleshooting

| Message | Meaning |
| --- | --- |
| `refusing to run on a dirty tree` | commit, stash or delete the listed files; untracked files and ignored files other than tooling and caches count (`IGNORED_OK`) |
| `stale .venv-test: run make venv-test` | the venv does not match the committed pins (for example after a Dependabot bump): `make venv-test` or `make venv-testmin` |
| `HEAD ... is not signed by an allowed signer` | amend with `git commit --amend -S --no-edit`, or use `make ci-pr` for someone else's PR |
| `signing did not finish within 60 s` | the signing agent is waiting for a YubiKey touch or is not running |
| `no signed local CI evidence for <sha>` | the note was never published: `make ci && make ci-publish` |
| `stale evidence` | the note belongs to another commit or tree: rerun `make ci` on this commit |
| `lacks required step(s)` | the policy at this commit requires a step the evidence does not have |
