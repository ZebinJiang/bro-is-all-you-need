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

clean:
	find . -name "*.pyc" | xargs rm -f && \
	find . -name "__pycache__" | xargs rm -rf

check:
	black --check .
	ruff check --show-source .

autoformat:
	black .
	ruff check --fix-only --show-fixes .

.PHONY: genesis-check

genesis-check:
	black --check --line-length 100 --workers 1 genesisvla tests/meta tests/core tests/config
	ruff check --config 'line-length=100' genesisvla tests/meta tests/core tests/config
	pyright -p pyrightconfig.genesisvla.json
	pytest tests/meta/test_repo_policy.py tests/core tests/config -v
