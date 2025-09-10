# DevContainer Service Manager - Development Tasks

.PHONY: help install test test-unit test-integration test-contract test-state test-performance test-edge lint format clean coverage validate-contracts

# Default target
help:
	@echo "DevContainer Service Manager - Development Tasks"
	@echo ""
	@echo "Installation:"
	@echo "  install          Install package and dependencies"
	@echo "  install-dev      Install with development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests (requires Docker)"
	@echo "  test-contract    Run contract fulfillment tests"
	@echo "  test-state       Run state simulation tests"
	@echo "  test-performance Run performance tests"
	@echo "  test-edge        Run edge case tests"
	@echo "  validate-contracts Validate service manager contracts"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             Run linting (ruff)"
	@echo "  format           Format code (black + ruff)"
	@echo "  typecheck        Run type checking (mypy)"
	@echo "  coverage         Generate test coverage report"
	@echo ""
	@echo "Utilities:"
	@echo "  clean            Clean build artifacts"
	@echo "  build            Build package"

# Installation targets
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# Testing targets
test:
	python tests/test_runner.py --category all

test-unit:
	python tests/test_runner.py --category unit

test-integration:
	python tests/test_runner.py --category integration

test-contract:
	python tests/test_runner.py --category contract

test-state:
	python tests/test_runner.py --category state

test-performance:
	python tests/test_runner.py --category performance

test-edge:
	python tests/test_runner.py --category edge

validate-contracts:
	python tests/test_runner.py --validate-contracts

# Quick pytest runs for development
pytest-unit:
	pytest tests/unit -v

pytest-integration:
	pytest tests/integration -v

pytest-all:
	pytest tests/ -v --cov=devcontainer_services --cov-report=term-missing

# Code quality targets
lint:
	ruff check src/ tests/

format:
	black src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy src/devcontainer_services

coverage:
	pytest tests/ --cov=devcontainer_services --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

# Utility targets
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:
	python -m build

# Development workflow
dev-setup: install-dev
	@echo "Development environment setup complete!"
	@echo "Run 'make test' to run the test suite"
	@echo "Run 'make validate-contracts' to verify service manager contracts"

# CI/CD targets
ci-test: lint typecheck test validate-contracts
	@echo "All CI checks passed!"

# Docker-based testing (for CI environments)
test-docker:
	docker run --rm -v $(PWD):/workspace -w /workspace python:3.12 \
		bash -c "pip install -e .[dev] && make test"

# Release targets (for maintainers)
check-release: clean lint typecheck test validate-contracts build
	@echo "Release checks complete - ready for publication"
