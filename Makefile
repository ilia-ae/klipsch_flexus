# Minimal entry point for the Molecule harness (PART A). The full Makefile (local CI) replaces this
# file and keeps including mk/*.mk. Compatible with GNU make 3.81 (macOS) and 4.x.
.DEFAULT_GOAL := help

include mk/*.mk

.PHONY: help
help: ## List targets
	@awk 'BEGIN { FS = ":.*## " } /^[a-zA-Z0-9_%-]+:.*## / { printf "  %-20s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
