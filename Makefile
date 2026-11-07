# klipsch_flexus developer entry points. All CI runs here, on the owner's Mac;
# GitHub only verifies signed evidence (see docs/TESTING.md, "Local CI and
# signed evidence"). GNU make 3.81 compatible.

SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
UV ?= uv
UVX ?= uvx
PYTHON_LATEST ?= 3.14
PYTHON_MIN ?= 3.12
RUFF_VERSION := 0.17.2
RUFF := $(UVX) ruff@$(RUFF_VERSION)
RUFF_PATHS := custom_components/klipsch_flexus tools tests scripts
ACTIONLINT := $(UVX) --from actionlint-py==1.7.7.23 actionlint
SHELLCHECK_FROM := shellcheck-py==0.10.0.1
YAMLLINT := $(UVX) yamllint==1.38.0
YAMLLINT_GITHUB := {extends: default, rules: {line-length: {max: 200}, document-start: disable, truthy: {check-keys: false}}}

# Official images, pinned by multi-arch index digest. Both publish linux/amd64
# only; Docker Desktop on Apple Silicon runs them under emulation.
DOCKER_PLATFORM := linux/amd64
HASSFEST_IMAGE := ghcr.io/home-assistant/hassfest@sha256:f9ac52cfe0f7b8770334f191e6713aa9f10f0906a989bd38d75a4933534144c7
HACS_IMAGE := ghcr.io/hacs/action@sha256:187499a09c5d41f9f0d42ff80d203ed87b974c028290140913b61e005fb0aab2
REPOSITORY := ilia-ae/klipsch_flexus
REF ?= main

LOCAL_CI := $(PYTHON) -I scripts/local_ci.py

# Extra targets (mk/ansible.mk: lint-ansible, molecule-scenarios, ...).
include $(wildcard mk/*.mk)

.PHONY: help venv-test venv-testmin test test-latest test-min ruff format ruff-version \
	lint-workflows hassfest hassfest-image hacs ci ci-run ci-sign ci-verify ci-publish ci-pr ci-selftest release-tag

help: ## List the targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'

# --- Python tests ------------------------------------------------------------

venv-test: ## Recreate .venv-test (Python 3.14, current HA) from requirements_test.txt
	rm -rf .venv-test
	$(UV) venv --quiet --python $(PYTHON_LATEST) .venv-test
	$(UV) pip install --quiet --python .venv-test/bin/python -r requirements_test.txt

venv-testmin: ## Recreate .venv-testmin (Python 3.12, oldest supported HA)
	rm -rf .venv-testmin
	$(UV) venv --quiet --python $(PYTHON_MIN) .venv-testmin
	$(UV) pip install --quiet --python .venv-testmin/bin/python -r .github/ci/requirements_test_min.txt

test: test-latest test-min ## pytest on both Home Assistant versions

test-latest: ## pytest on the pinned current Home Assistant (.venv-test)
	@test -x .venv-test/bin/python || { echo "missing .venv-test: run make venv-test" >&2; exit 1; }
	.venv-test/bin/python -m pytest tests -q -ra

test-min: ## pytest on the oldest supported Home Assistant (.venv-testmin)
	@test -x .venv-testmin/bin/python || { echo "missing .venv-testmin: run make venv-testmin" >&2; exit 1; }
	.venv-testmin/bin/python -m pytest tests -q -ra

# --- Lint and validation -----------------------------------------------------

ruff: ## ruff check + format --check (pinned ruff)
	$(RUFF) check $(RUFF_PATHS)
	$(RUFF) format --check $(RUFF_PATHS)

format: ## Apply ruff fixes and formatting
	$(RUFF) check --fix $(RUFF_PATHS)
	$(RUFF) format $(RUFF_PATHS)

ruff-version:
	@$(RUFF) --version

lint-workflows: ## actionlint (with shellcheck) + yamllint on .github (pinned, via uvx)
	@sc="$$($(UVX) --from $(SHELLCHECK_FROM) python -c 'import os, sys; print(os.path.join(os.path.dirname(sys.executable), "shellcheck"))')"; \
	echo "$(ACTIONLINT) -shellcheck $$sc .github/workflows/*.yaml"; \
	$(ACTIONLINT) -shellcheck "$$sc" .github/workflows/*.yaml
	$(YAMLLINT) -d '$(YAMLLINT_GITHUB)' .github

# hassfest sees only the tracked integration files (a clean export, no caches),
# mounted read-only into a throwaway klipsch-flexus-* container.
hassfest: ## Validate the integration with the pinned official hassfest container
	@set -euo pipefail; \
	tmp="$$(mktemp -d "$${TMPDIR:-/tmp}/klipsch-flexus-hassfest.XXXXXX")"; \
	trap 'rm -rf "$$tmp"' EXIT; \
	git ls-files -z -- custom_components | tar --null -T - -cf - | tar -xf - -C "$$tmp"; \
	echo "hassfest $(HASSFEST_IMAGE) on $$(git ls-files -- custom_components | wc -l | tr -d ' ') files"; \
	docker run --rm --platform $(DOCKER_PLATFORM) --name "klipsch-flexus-hassfest-$$$$" \
		-v "$$tmp:/github/workspace:ro" $(HASSFEST_IMAGE)

hassfest-image:
	@id="$$(docker image inspect --format '{{.Id}}' $(HASSFEST_IMAGE) 2>/dev/null | head -n 1)"; \
	echo "$(HASSFEST_IMAGE) id=$${id:-not-pulled}"

# Not part of the signed policy: the HACS action validates the repository as
# GitHub serves it (API), never the local tree, so it cannot attest a commit.
# Anonymous by default; HACS_TOKEN=$$(gh auth token) only if rate-limited.
hacs: ## HACS validation of the PUSHED repository state (REF=main|vX.Y.Z|<sha>)
	INPUT_GITHUB_TOKEN="$${HACS_TOKEN:-}" docker run --rm --platform $(DOCKER_PLATFORM) \
		--name "klipsch-flexus-hacs-$$$$" -e INPUT_GITHUB_TOKEN \
		-e REPOSITORY=$(REPOSITORY) -e CATEGORY=integration -e REPOSITORY_REF=$(REF) $(HACS_IMAGE)

# --- Local CI and signed evidence ------------------------------------------

ci: ## Run every .ci/local-ci.json step on the clean, signed HEAD and sign the evidence
	$(LOCAL_CI) run
	$(LOCAL_CI) sign

ci-run: ## Only run the steps (no signature)
	$(LOCAL_CI) run

ci-sign: ## Only sign the evidence of the last run for HEAD
	$(LOCAL_CI) sign

ci-verify: ## Verify HEAD's signed evidence exactly as GitHub will
	$(LOCAL_CI) verify

ci-publish: ## Push the signed evidence note (refs/notes/local-ci only); DISPATCH=1 also asks GitHub to verify
	$(LOCAL_CI) publish $(if $(DISPATCH),--dispatch)

ci-pr: ## Test PR=<n> in a temp worktree, sign, publish and dispatch verification (CONFIRM=1 if it touches CI)
	@test -n "$(PR)" || { echo "usage: make ci-pr PR=<number>" >&2; exit 2; }
	$(LOCAL_CI) pr --number $(PR) $(if $(CONFIRM),--confirm)

ci-selftest: ## Unit tests of the runner and the verifier (throwaway keys)
	$(PYTHON) -I scripts/test_local_ci.py

release-tag: ## Create the signed annotated release tag vVERSION for HEAD (VERSION=x.y.z)
	@test -n "$(VERSION)" || { echo "usage: make release-tag VERSION=x.y.z" >&2; exit 2; }
	@manifest="$$($(PYTHON) -I -c 'import json; print(json.load(open("custom_components/klipsch_flexus/manifest.json"))["version"])')"; \
	test "$$manifest" = "$(VERSION)" || { echo "manifest.json version is $$manifest, not $(VERSION)" >&2; exit 1; }
	$(LOCAL_CI) verify
	git tag -s "v$(VERSION)" -m "v$(VERSION)"
	git verify-tag "v$(VERSION)"
	@echo "next: make ci-publish && git push origin main v$(VERSION)"
