.PHONY: help venv install dev format lint type-check security quality test test-integration test-all test-unsafe clean

help:
	@echo "Available commands:"
	@echo "  make venv            - Create virtual environment"
	@echo "  make install         - Install dependencies"
	@echo "  make dev             - Install with dev dependencies"
	@echo "  make format          - Format code with ruff"
	@echo "  make lint            - Lint code with ruff"
	@echo "  make type-check      - Type check with mypy"
	@echo "  make security        - Run security checks"
	@echo "  make quality         - Run all quality checks (format, lint, type-check)"
	@echo "  make test            - Run unit tests only"
	@echo "  make test-integration- Run integration tests only"
	@echo "  make test-all        - Run all tests"
	@echo "  make test-unsafe     - Run tests on host (debugging only)"
	@echo "  make clean           - Clean build artifacts"

venv:
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv .venv; \
		echo "Virtual environment created at .venv"; \
		echo "Activate with: source .venv/bin/activate"; \
	else \
		echo "Virtual environment already exists at .venv"; \
	fi

install: venv
	.venv/bin/pip install -e .

dev: venv
	.venv/bin/pip install -e ".[dev]"

format:
	.venv/bin/ruff format src/ tests/
	.venv/bin/ruff check --fix src/ tests/

lint:
	.venv/bin/ruff check src/ tests/

type-check:
	.venv/bin/mypy src/

security:
	@echo "Security checks not yet implemented"

quality: format lint type-check
	@echo "✓ Quality checks passed"

test:
	.venv/bin/pytest tests/unit -v

test-integration:
	.venv/bin/pytest tests/integration -v

test-all:
	.venv/bin/pytest tests/ -v

test-unsafe:
	@echo "Warning: Running tests on host (not in container)"
	.venv/bin/pytest tests/ -v

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
