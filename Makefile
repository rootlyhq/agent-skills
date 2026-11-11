.DEFAULT_GOAL := help

PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: help setup generate lint lint-fix test check public-check staged-check outgoing-check export

help:
	@echo "make setup        Create a virtual environment and install pinned tools"
	@echo "make generate     Regenerate platform manifests and shared skill resources"
	@echo "make lint         Check Python imports, unused names, and modern syntax"
	@echo "make lint-fix     Apply safe lint fixes outside calibration-pinned files"
	@echo "make test         Run the offline static suite"
	@echo "make check        Run lint, metadata, generated-file, and static checks"
	@echo "make public-check Run the required configured publication scan"
	@echo "make staged-check Scan the exact index with configured private markers"
	@echo "make outgoing-check RANGE=origin/main..HEAD  Scan every outgoing commit"
	@echo "make export       Export a local candidate without publishing"

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV)

setup: $(VENV_PYTHON)
	$(VENV_PYTHON) -m pip install -r tools/requirements-dev.txt

generate:
	$(VENV_PYTHON) tools/scripts/build_package.py

lint:
	$(VENV_PYTHON) -m ruff check tools

lint-fix:
	$(VENV_PYTHON) -m ruff check --fix tools \
	  --extend-exclude tools/scripts/fidelity_judge.py \
	  --extend-exclude tools/scripts/fidelity_contract.py \
	  --extend-exclude tools/scripts/fidelity_gate.py \
	  --extend-exclude tools/scripts/fidelity_matrix.py \
	  --extend-exclude tools/scripts/fidelity_inputs.py

test:
	$(VENV_PYTHON) -m unittest discover -s tools/tests/static -v

check: lint
	$(VENV_PYTHON) tools/scripts/check_release_metadata.py
	$(VENV_PYTHON) tools/scripts/build_package.py --check
	$(VENV_PYTHON) tools/scripts/validate_skills.py
	$(VENV_PYTHON) tools/scripts/check_public_tree.py
	$(MAKE) test

public-check:
	$(VENV_PYTHON) tools/scripts/check_public_tree.py --require-private-markers

staged-check:
	$(VENV_PYTHON) tools/scripts/check_public_tree.py --staged --require-private-markers

outgoing-check:
	@test -n "$(RANGE)" || { echo "Set RANGE, for example origin/main..HEAD"; exit 1; }
	$(VENV_PYTHON) tools/scripts/check_public_tree.py --range "$(RANGE)" --require-private-markers

export:
	$(VENV_PYTHON) tools/scripts/export_release.py
