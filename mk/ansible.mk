# Ansible / Molecule targets of the HACS-like integration harness (docs/TESTING.md, "Molecule").
# Test-only: every inventory is a Molecule container; nothing here touches a real Home Assistant.
# Included by the top-level Makefile. Compatible with GNU make 3.81 (macOS) and 4.x (Linux).
#
#   make venv collections lint-ansible
#   make molecule-scenarios SCENARIOS="klipsch_flexus_install/fresh klipsch_flexus_install/upgrade"
#   make molecule-list
#   make molecule-cleanup SCENARIOS=klipsch_flexus_install/fresh   (after an interrupted run)

ANSIBLE_PYTHON ?= /opt/homebrew/bin/python3.13
ANSIBLE_VENV   ?= .venv
# Targets for `make molecule-scenarios` / `make molecule-cleanup`: "<role>/<scenario> ...".
SCENARIOS ?=
# Inner dev loop on a kept container: make molecule-stage STAGE=verify S=<role>/<scenario>
STAGE ?=
S ?=

ANSIBLE_ROOT     := $(CURDIR)
ANSIBLE_VENV_BIN := $(abspath $(ANSIBLE_VENV))/bin
ANSIBLE_COLLECTIONS_DIR   := ansible/collections

# The venv runs every tool: molecule spawns ansible-playbook by name.
ANSIBLE_ENV := PATH="$(ANSIBLE_VENV_BIN):$$PATH" \
	ANSIBLE_COLLECTIONS_PATH="$(ANSIBLE_ROOT)/$(ANSIBLE_COLLECTIONS_DIR)" \
	ANSIBLE_CONFIG="$(ANSIBLE_ROOT)/ansible/ansible.cfg" \
	PIP_DISABLE_PIP_VERSION_CHECK=1 \
	PYTHONDONTWRITEBYTECODE=1

.PHONY: venv collections lint-ansible molecule-scenarios molecule-stage molecule-list molecule-cleanup molecule-images

# venv and collections compare what is installed with the committed pins
# (scripts/check_pins.py), not file times: a worktree checkout, or a branch with
# other pins, must neither skip an install nor keep tooling the commit does not pin.
venv: ## Create .venv (Python 3.13) with the pinned requirements-dev.txt
	@if test -x $(ANSIBLE_VENV)/bin/python && $(ANSIBLE_VENV_BIN)/python -I scripts/check_pins.py requirements-dev.txt 2>/dev/null; then \
		echo "$(ANSIBLE_VENV) matches requirements-dev.txt"; \
	else \
		set -e; \
		test -x $(ANSIBLE_VENV)/bin/python || $(ANSIBLE_PYTHON) -m venv $(ANSIBLE_VENV); \
		$(ANSIBLE_VENV_BIN)/pip install --disable-pip-version-check -r requirements-dev.txt; \
		$(ANSIBLE_VENV_BIN)/python -I scripts/check_pins.py requirements-dev.txt; \
	fi

collections: venv ## Install the pinned collections into ansible/collections
	@if $(ANSIBLE_VENV_BIN)/python -I scripts/check_pins.py --collections ansible/requirements.yml $(ANSIBLE_COLLECTIONS_DIR) 2>/dev/null; then \
		echo "$(ANSIBLE_COLLECTIONS_DIR) matches ansible/requirements.yml"; \
	else \
		set -e; \
		$(ANSIBLE_VENV_BIN)/ansible-galaxy collection install --force -r ansible/requirements.yml -p $(ANSIBLE_COLLECTIONS_DIR); \
		$(ANSIBLE_VENV_BIN)/python -I scripts/check_pins.py --collections ansible/requirements.yml $(ANSIBLE_COLLECTIONS_DIR); \
	fi

lint-ansible: collections ## yamllint --strict + ansible-lint (production profile) on ansible/
	$(ANSIBLE_ENV) $(ANSIBLE_VENV_BIN)/yamllint --strict ansible mk .yamllint .ansible-lint
	$(ANSIBLE_ENV) $(ANSIBLE_VENV_BIN)/ansible-lint ansible

molecule-scenarios: collections ## SCENARIOS="<role>/<scenario> ..." full create->destroy, one at a time
	@if [ -z "$(SCENARIOS)" ]; then echo 'set SCENARIOS, e.g. make molecule-scenarios SCENARIOS="klipsch_flexus_install/fresh"' >&2; exit 2; fi
	$(ANSIBLE_ENV) scripts/molecule.sh $(SCENARIOS)

molecule-stage: collections ## STAGE=create|prepare|converge|idempotence|verify|destroy S=<role>/<scenario> (kept container)
	@if [ -z "$(STAGE)" ] || [ -z "$(S)" ]; then echo 'set STAGE and S, e.g. make molecule-stage STAGE=verify S=klipsch_flexus_install/fresh' >&2; exit 2; fi
	$(ANSIBLE_ENV) scripts/molecule.sh --stage $(STAGE) $(S)

molecule-list: ## List every Molecule scenario (<role>/<scenario>)
	@scripts/molecule.sh --list

# One line, for the local CI evidence: the pinned Home Assistant images the scenarios run.
molecule-images:
	@grep -h '^ *image: ' ansible/roles/*/molecule/*/molecule.yml | sed 's/^ *image: *//' | sort -u | tr '\n' ' ' | sed 's/ $$//'; echo

molecule-cleanup: ## Remove leftover klipsch-flexus-* containers (+ state) of SCENARIOS, or of every scenario
	scripts/molecule.sh --cleanup $(SCENARIOS)
