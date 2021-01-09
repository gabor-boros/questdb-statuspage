.PHONY: clean clean-test clean-pyc clean-build clean-mypy help
.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

clean: clean-build clean-pyc clean-test clean-mypy ## remove all build, test, coverage and Python artifacts

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-mypy: ## remove mypy related artifacts
	rm -rf .mypy_cache

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/ \
	.coverage \
	htmlcov/ \
	.pytest_cache

format: ## run formatters on the package
	isort --apply -rc app tests
	black app tests

lint: ## run linters against the package
	mypy app
	pylint app

test-unit: ## run unit tests and generate coverage
	coverage run -m pytest -m "not integration" -vv
	coverage report

test-integration: ## run unit tests and generate coverage
	coverage run -m pytest -m "integration" -vv
	coverage report

test: ## run all tests and generate coverage
	coverage run -m pytest -vv
	coverage report
	coverage xml
