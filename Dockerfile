# Use lightweight Python 3.11 image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy only dependency files first (for build cache)
COPY backend/pyproject.toml backend/poetry.lock ./backend/

# Install dependencies
WORKDIR /app/backend
RUN poetry config virtualenvs.in-project true \
 && poetry install --no-interaction --no-ansi

# Copy rest of your backend code
COPY backend /app/backend

# Expose default FastAPI port
EXPOSE 8000

# Start the app using the virtualenv’s python
CMD ["./.venv/bin/python", "serve.py"]
