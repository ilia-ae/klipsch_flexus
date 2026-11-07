# Contributing

Thanks for helping. Issues and pull requests are welcome. Questions go to
[GitHub Discussions](https://github.com/ilia-ae/klipsch_flexus/discussions)
(see [SUPPORT.md](SUPPORT.md)). Everyone taking part follows the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Before you open a pull request

```bash
make venv-test venv-testmin   # once (needs uv)
make test                     # pytest on the current and the oldest supported Home Assistant
make ruff                     # lint + format check; `make format` fixes what it can
```

Docker is optional for contributors. `make hassfest` runs hassfest on the
integration, if you have Docker. It uses the official image pinned by digest,
or rebuilds it from the same source on an arm64 machine.

You do not need a signing key, and you do not need to run `make ci`.

Some rules for the content of a change:

- **UI text**: `strings.json` and every file in
  `custom_components/klipsch_flexus/translations/` must have the same keys
  (`tests/test_translations.py` checks this).
- **README**: `README.md` (English) is the source. The translations in
  `docs/README_{de,es,fr,it,nl,pt,ru,zh}.md` must match it section by section. Update them
  if you can; otherwise say so in the pull request and the maintainer will.
- **Tests**: keep them self-contained (no network, no writes outside temporary
  directories). They run on the maintainer's machine.

## How your pull request is checked

This repository runs no tests on GitHub. All CI runs on the maintainer's machine,
and GitHub only verifies signed evidence of that run. See
[docs/TESTING.md](docs/TESTING.md#local-ci-and-signed-evidence) for details.

Your pull request shows a check named **Verify signed local CI (advisory)**. It
fails at first, which is expected: your commits are not signed by the maintainer,
and no evidence exists for them yet. It is only advisory, because GitHub runs it
from the workflow file in your PR. The result that counts is the commit status
**`local-ci/verified`**. After review, the maintainer does two things:

1. Runs `make ci-pr PR=<number>` locally. It tests your PR head, signs the
   evidence and asks GitHub to verify it. That sets the `local-ci/verified`
   status on your commit.
2. Merges the PR locally with a signed commit, so `main` stays owner-signed.
   GitHub's merge button is not used: its commits are not signed by the owner
   and fail verification on `main`.

A PR that changes anything other than the integration code, `tests/test_*.py`
or the documentation (for example a `conftest.py`, the `Makefile`, `mk/`,
`pyproject.toml`, requirement files, `.ci/`, `scripts/`, `ansible/` or
`.github/`) gets an extra manual review before it is tested, because those files
can change what the checks do.

## Releases

Users install and update the integration only through HACS, from GitHub
releases. A merged change reaches users like this:

1. It ships first in a **beta**: a GitHub pre-release tagged `vX.Y.Z-beta.N`.
   HACS offers it only to users who turned on the **Pre-release** switch for
   this repository (see [Beta versions](README.md#beta-versions)).
2. A stable release `vX.Y.Z` follows when the maintainer decides the beta is
   ready. Every release tag is a signed annotated tag, and the release workflow
   checks the signed local CI evidence for its commit
   ([docs/TESTING.md](docs/TESTING.md#releases)).

If you can, try the beta that contains your change and report back in the pull
request or its issue.
