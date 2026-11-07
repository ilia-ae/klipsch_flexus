# Contributing

Thanks for helping. Issues and pull requests are welcome.

## Before you open a pull request

```bash
make venv-test venv-testmin   # once (needs uv)
make test                     # pytest on the current and the oldest supported Home Assistant
make ruff                     # lint + format check; `make format` fixes what it can
```

Docker is optional for contributors. `make hassfest` runs the official
hassfest container on the integration, if you have Docker.

You do not need a signing key, and you do not need to run `make ci`.

## How your pull request is checked

This repository runs no tests on GitHub. All CI runs on the maintainer's machine,
and GitHub only verifies signed evidence of that run. See
[docs/TESTING.md](docs/TESTING.md#local-ci-and-signed-evidence) for details.

So the **Verify signed local CI** check on your pull request **fails at first**.
That is expected: your commits are not signed by the maintainer, and no evidence
exists for them yet. After review, the maintainer does two things:

1. Runs `make ci-pr PR=<number>` locally. It tests your PR head, signs the
   evidence and asks GitHub to verify it. That sets the `local-ci/verified`
   status on your commit.
2. Merges the PR locally with a signed commit, so `main` stays owner-signed.

A PR that changes the CI machinery (`.ci/`, `scripts/`, `Makefile`, `mk/`,
`.github/`) gets an extra manual review before it is tested.
