.PHONY: help install-uv sync clean
.PHONY: test test-cov format lint check
.PHONY: build install

# Default target
help:
	@echo "Arrowhead Python SDK - uv-managed Python SDK and CLI"
	@echo ""
	@echo "Setup:"
	@echo "  install-uv     Install uv if not already installed"
	@echo "  sync           Download dependencies"
	@echo "  clean          Clean cache and temporary files"
	@echo ""
	@echo "Development:"
	@echo "  test           Run tests"
	@echo "  test-cov       Run tests with coverage"
	@echo "  format         Format code with ruff"
	@echo "  lint           Lint code with ruff"
	@echo "  check          Type check with pyright"
	@echo ""
	@echo "Build:"
	@echo "  build          Build the package"
	@echo "  install        Install package locally"

install-uv:
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "uv (https://astral.sh/uv/) is required by this project, but is not installed."; \
		read -p "Do you want to install uv? (y/n): " choice; \
		if [ "$$choice" == "y" ]; then \
			echo "Installing uv..."; \
			curl -LsSf https://astral.sh/uv/install.sh | sh; \
		fi \
	fi

sync: install-uv
	@uv sync

clean:
	@echo "Cleaning cache and temporary files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.pyd" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/

# Test targets
test: install-uv
	@echo "Running tests..."
	@uv run pytest

test-cov: install-uv
	@echo "Running tests with coverage..."
	@uv run pytest --cov=arrowhead --cov-report=term-missing

# Development targets
format: install-uv
	@echo "Formatting code with ruff..."
	@uv run ruff format .

lint: install-uv
	@echo "Linting code with ruff..."
	@uv run ruff check .

check: install-uv
	@echo "Type checking with pyright..."
	@uv run pyright

# Build targets
build: sync
	@echo "Building package..."
	@uv build

install: sync
	@echo "Installing package locally..."
	@uv pip install -e .