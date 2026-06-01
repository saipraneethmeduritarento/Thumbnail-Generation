# Use the official Python image from the Docker Hub
FROM python:3.12-slim-bullseye

# Set environment variables
ENV POETRY_VERSION=1.8.3
ENV VIRTUAL_ENV=/opt/venv

# Install Poetry
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Create a virtual environment
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Create non-root user
RUN addgroup --system appuser && adduser --system --ingroup appuser appuser

# Set the working directory in the container
WORKDIR /app

# Copy the poetry.lock and pyproject.toml files first to leverage Docker cache
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-root --no-dev

# Copy the entire application code into the container
COPY ./app ./app

# Change ownership of app directory
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the port that the FastAPI app will run on
EXPOSE 8000

# Command to run the FastAPI application using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
