## What and why

<!-- What does this change, and why? Link the issue, for example "Fixes #123". -->

## How you tested it

<!-- For example: make test and make ruff passed; tested on a CORE 300 with firmware 1.1.3.x and Home Assistant 2026.10. -->

- [ ] `make test` passes (pytest on the current and the oldest supported Home Assistant)
- [ ] `make ruff` passes
- [ ] Tested on a real soundbar (model and firmware: )

## Notes

- The check **Verify signed local CI (advisory)** fails on pull requests at first. That is expected. The maintainer tests your PR locally and then sets the commit status `local-ci/verified`. See [CONTRIBUTING.md](https://github.com/ilia-ae/klipsch_flexus/blob/main/CONTRIBUTING.md).
- You do not need a signing key. The maintainer merges with a signed commit.
