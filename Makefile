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
RUFF_PATHS := custom_components/klipsch_flexus tools tests scripts ansible
ACTIONLINT := $(UVX) --from actionlint-py==1.7.7.23 actionlint
SHELLCHECK_FROM := shellcheck-py==0.10.0.1
YAMLLINT := $(UVX) yamllint==1.38.0
YAMLLINT_GITHUB := {extends: default, rules: {line-length: {max: 200}, document-start: disable, truthy: {check-keys: false}}}

# Official images, pinned by multi-arch index digest, with the upstream commit
# and Dockerfile each was built from (its build provenance). Both images are
# linux/amd64 only; scripts/pinned_image.sh uses the official image where Docker
# runs amd64 natively and otherwise builds that Dockerfile at that commit, once,
# for the native architecture (IMAGES=official|local overrides).
HASSFEST_IMAGE := ghcr.io/home-assistant/hassfest@sha256:f9ac52cfe0f7b8770334f191e6713aa9f10f0906a989bd38d75a4933534144c7
HASSFEST_SOURCE := https://github.com/home-assistant/core.git\#74cf5a49c63ed8d4d87717844bf14f79c28c9cea
HASSFEST := scripts/pinned_image.sh $(HASSFEST_IMAGE) $(HASSFEST_SOURCE) script/hassfest/docker/Dockerfile klipsch-flexus-hassfest
HACS_IMAGE := ghcr.io/hacs/action@sha256:187499a09c5d41f9f0d42ff80d203ed87b974c028290140913b61e005fb0aab2
HACS_SOURCE := https://github.com/hacs/integration.git\#0704ffc6e790b9714c82384d8c564266434ff6f9
HACS := scripts/pinned_image.sh $(HACS_IMAGE) $(HACS_SOURCE) action/Dockerfile klipsch-flexus-hacs
REPOSITORY := ilia-ae/klipsch_flexus
REF ?= main

LOCAL_CI := $(PYTHON) -I scripts/local_ci.py

# Extra targets (mk/ansible.mk: lint-ansible, molecule-scenarios, ...).
include $(wildcard mk/*.mk)

.PHONY: help venv-test venv-testmin test test-latest test-min ruff format ruff-version \
	lint-workflows hassfest hassfest-image hacs ci ci-run ci-sign ci-verify ci-publish ci-pr ci-selftest release-tag release-beta-next

help: ## List the targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'

# --- Python tests ------------------------------------------------------------

venv-test: ## Recreate .venv-test (Python 3.14, current HA) from requirements_test.txt
	rm -rf .venv-test
	$(UV) venv --quiet --python $(PYTHON_LATEST) .venv-test
	$(UV) pip install --quiet --python .venv-test/bin/python -r requirements_test.txt
	.venv-test/bin/python -I scripts/check_pins.py requirements_test.txt

venv-testmin: ## Recreate .venv-testmin (Python 3.12, oldest supported HA)
	rm -rf .venv-testmin
	$(UV) venv --quiet --python $(PYTHON_MIN) .venv-testmin
	$(UV) pip install --quiet --python .venv-testmin/bin/python -r .github/ci/requirements_test_min.txt
	.venv-testmin/bin/python -I scripts/check_pins.py .github/ci/requirements_test_min.txt

test: test-latest test-min ## pytest on both Home Assistant versions

# The venvs are not rebuilt per run, so each pytest target first checks that its
# venv has exactly what the committed requirements file pins (a Dependabot bump
# of Home Assistant must not be tested, and signed, on the previous one).
test-latest: ## pytest on the pinned current Home Assistant (.venv-test)
	@test -x .venv-test/bin/python || { echo "missing .venv-test: run make venv-test" >&2; exit 1; }
	@.venv-test/bin/python -I scripts/check_pins.py requirements_test.txt || { echo "stale .venv-test: run make venv-test" >&2; exit 1; }
	.venv-test/bin/python -m pytest tests -q -ra

test-min: ## pytest on the oldest supported Home Assistant (.venv-testmin)
	@test -x .venv-testmin/bin/python || { echo "missing .venv-testmin: run make venv-testmin" >&2; exit 1; }
	@.venv-testmin/bin/python -I scripts/check_pins.py .github/ci/requirements_test_min.txt || { echo "stale .venv-testmin: run make venv-testmin" >&2; exit 1; }
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

lint-workflows: ## actionlint + shellcheck on workflows and scripts/*.sh, yamllint on .github (pinned, via uvx)
	@sc="$$($(UVX) --from $(SHELLCHECK_FROM) python -c 'import os, sys; print(os.path.join(os.path.dirname(sys.executable), "shellcheck"))')"; \
	echo "$(ACTIONLINT) -shellcheck $$sc .github/workflows/*.yaml"; \
	$(ACTIONLINT) -shellcheck "$$sc" .github/workflows/*.yaml; \
	echo "shellcheck scripts/*.sh"; \
	"$$sc" scripts/*.sh
	$(YAMLLINT) -d '$(YAMLLINT_GITHUB)' .github

# hassfest sees only the tracked integration files (a clean export, no caches),
# mounted read-only into a throwaway klipsch-flexus-* container.
hassfest: ## Validate the integration with the pinned official hassfest image (or its native rebuild)
	@set -euo pipefail; \
	image="$$($(HASSFEST))"; \
	tmp="$$(mktemp -d "$${TMPDIR:-/tmp}/klipsch-flexus-hassfest.XXXXXX")"; \
	trap 'rm -rf "$$tmp"' EXIT; \
	git ls-files -z -- custom_components | tar --null -T - -cf - | tar -xf - -C "$$tmp"; \
	echo "hassfest $$image on $$(git ls-files -- custom_components | wc -l | tr -d ' ') files"; \
	docker run --rm --name "klipsch-flexus-hassfest-$$$$" -v "$$tmp:/github/workspace:ro" "$$image"

hassfest-image:
	@image="$$(IMAGES=$${IMAGES:-auto} $(HASSFEST) 2>/dev/null)"; \
	echo "$$image id=$$(docker image inspect --format '{{.Id}}' "$$image" 2>/dev/null | head -n 1)"

# Not part of the signed policy: the HACS action validates the repository as
# GitHub serves it (API), never the local tree, so it cannot attest a commit.
# GitHub runs it on pushed commits (.github/workflows/validate.yaml, same digest).
# The action refuses to run without a token (an empty one gets HTTP 401). It
# takes HACS_TOKEN (best: a fine-grained token with read-only public access),
# else `gh auth token`, read at run time and passed by environment, never argv.
hacs: ## HACS validation of the PUSHED repository state (REF=main|vX.Y.Z|<sha>)
	@set -euo pipefail; \
	image="$$($(HACS))"; \
	echo "HACS validation of $(REPOSITORY)@$(REF) with $$image"; \
	INPUT_GITHUB_TOKEN="$${HACS_TOKEN:-$$(gh auth token)}" docker run --rm --name "klipsch-flexus-hacs-$$$$" -e INPUT_GITHUB_TOKEN \
		-e REPOSITORY=$(REPOSITORY) -e CATEGORY=integration -e REPOSITORY_REF=$(REF) "$$image"

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

ci-pr: ## Test PR=<n> in a temp worktree, sign, publish, dispatch verification (CONFIRM=1 beyond code/tests/docs)
	@test -n "$(PR)" || { echo "usage: make ci-pr PR=<number>" >&2; exit 2; }
	$(LOCAL_CI) pr --number $(PR) $(if $(CONFIRM),--confirm)

ci-selftest: ## Unit tests of the runner and the verifier (throwaway keys)
	$(PYTHON) -I scripts/test_local_ci.py

MANIFEST_VERSION = $(PYTHON) -I -c 'import json; print(json.load(open("custom_components/klipsch_flexus/manifest.json"))["version"])'

# Stable x.y.z (a normal GitHub release, marked Latest) only on the owner's word;
# x.y.z-beta.n becomes a GitHub pre-release (.github/workflows/release.yaml).
release-tag: ## Create the signed annotated tag vVERSION for HEAD (VERSION=x.y.z or x.y.z-beta.n)
	@[[ "$(VERSION)" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-beta\.[0-9]+)?$$ ]] || { echo "usage: make release-tag VERSION=x.y.z (stable) or VERSION=x.y.z-beta.n (beta)" >&2; exit 2; }
	@manifest="$$($(MANIFEST_VERSION))"; \
	test "$$manifest" = "$(VERSION)" || { echo "manifest.json version is $$manifest, not $(VERSION)" >&2; exit 1; }
	$(LOCAL_CI) verify
	git tag -s "v$(VERSION)" -m "v$(VERSION)"
	git verify-tag "v$(VERSION)"
	@echo "next: make ci-publish && git push origin main v$(VERSION)"

# Reads local tags only: run `git fetch --tags origin` first.
release-beta-next: ## Print the next free beta version x.y.z-beta.n (BASE=x.y.z, default: the manifest's x.y.z)
	@base="$(BASE)"; test -n "$$base" || base="$$($(MANIFEST_VERSION))"; base="$${base%%-*}"; \
	[[ "$$base" =~ ^[0-9]+\.[0-9]+\.[0-9]+$$ ]] || { echo "BASE must be x.y.z, got $$base" >&2; exit 2; }; \
	if git rev-parse --verify --quiet "refs/tags/v$$base" > /dev/null; then echo "v$$base is already released; pick a higher BASE" >&2; exit 1; fi; \
	last="$$(git tag -l "v$$base-beta.*" | sed 's/.*-beta\.//' | grep -E '^[0-9]+$$' | sort -n | tail -n 1)"; \
	echo "$$base-beta.$$(( $${last:-0} + 1 ))"
