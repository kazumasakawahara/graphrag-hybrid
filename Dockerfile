FROM python:3.12-slim AS base

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies (production only)
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY src/ ./src/
COPY server.py app.py ./

# Default: run MCP server in HTTP mode
EXPOSE 8100
CMD ["uv", "run", "python", "server.py", "--http"]
