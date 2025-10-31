# Use lightweight Python 3.11 image
FROM python:3.11-slim

# Set working directory
WORKDIR /app/backend

# Install Poetry
RUN pip install poetry

# Copy dependency files first (for build cache)
COPY backend/pyproject.toml backend/poetry.lock ./

# Install dependencies into in-project virtualenv
RUN poetry config virtualenvs.in-project true \
 && poetry install --no-interaction --no-ansi

# Copy the rest of the backend code
COPY backend /app/backend

# Bundle seed data so the app can populate an empty mounted volume at /app/db
COPY db /app/db-seed

# Expose FastAPI default port
EXPOSE 8000

# Run the app
CMD ["./.venv/bin/python", "serve.py"]
