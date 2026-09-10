# Dockerfile for Telegram Memory Bot
FROM python:3.12-slim AS builder

WORKDIR /app
RUN pip install uv

# Copy project files for dependency installation
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and sync again to include it
COPY src/ src/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Copy virtual environment and source code from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY alembic.ini .
COPY alembic/ alembic/

# Ensure the virtual environment is in PATH and src is in PYTHONPATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Run as non-root user
USER botuser

CMD ["python", "-m", "bot"]
