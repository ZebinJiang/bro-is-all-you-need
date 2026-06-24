.PHONY: help clean check autoformat
.DEFAULT: help

# Generates a useful overview/help message for various make features - add to this as necessary!
help:
	@echo "make clean"
	@echo "    Remove all temporary pyc/pycache files"
	@echo "make check"
	@echo "    Run code style and linting (black, ruff) *without* changing files!"
	@echo "make autoformat"
	@echo "    Apply formatting in place with black and fixable Ruff edits without failing on existing lint backlog."
	@echo "make genesis-check-local"
	@echo "    Run the GenesisVLA project-local quality wrapper."
	@echo "make genesis-check-bootstrap"
	@echo "    Create or refresh the GenesisVLA project-local quality environment offline."
	@echo "make genesis-wheelhouse-fill"
	@echo "    Fill the GenesisVLA quality wheelhouse with bounded online pip download."
	@echo "make genesis-build-check"
	@echo "    Build, install, and inspect the GenesisVLA wheel with project-local tools."
	@echo "make governance-check"
	@echo "    Run governance/meta policy checks separately from product checks."

clean:
	find . -name "*.pyc" | xargs rm -f && \
	find . -name "__pycache__" | xargs rm -rf

check:
	black --check .
	ruff check --show-source .

autoformat:
	black .
	ruff check --fix-only --show-fixes .

.PHONY: genesis-check genesis-check-local genesis-check-bootstrap genesis-wheelhouse-fill genesis-build-check governance-check

genesis-check-bootstrap:
	bash scripts/quality/bootstrap_project_local_tools.sh

genesis-wheelhouse-fill:
	bash scripts/quality/bootstrap_project_local_tools.sh --fill-wheelhouse

genesis-check:
	bash scripts/quality/genesis_check_project_local.sh

genesis-build-check:
	bash scripts/quality/genesis_build_verify_project_local.sh

governance-check:
	runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 tests/meta
	runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' tests/meta
	PYTHONPYCACHEPREFIX=runs/tmp/m1-tool-pip-tmp/python-cache-governance PYTEST_ADDOPTS='-p no:cacheprovider' runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -v

genesis-check-local:
	bash scripts/quality/genesis_check_project_local.sh
