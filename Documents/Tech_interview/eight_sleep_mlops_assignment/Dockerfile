# Use an official Python runtime as a parent image
FROM python:3.9-slim AS base

# Set environment variables to prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Create a working directory
WORKDIR /app

# Copy dependency definitions first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies.  Uvicorn[standard] installs Gunicorn and
# uvloop.  Torch can be heavy; consider using a CPU‑only version for
# slim images in production.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Generate the model inside the container at build time.  If the model
# already exists in the build context this command will overwrite it.
# Note: `create_model.py` writes a PyTorch `state_dict` to
# `inefficient_model.pt` (not a pickled model object). `main.py` expects
# a `state_dict` and will instantiate `InefficientModel` and call
# `load_state_dict(...)` at startup.
RUN python create_model.py

# Expose the port the app runs on
EXPOSE 8000

# Use a non‑root user for security (optional)
# RUN useradd -ms /bin/bash appuser
# USER appuser

# Define the default command to run the service with Uvicorn.  Use
# Gunicorn with Uvicorn workers for production deployments; here
# uvicorn alone suffices for demonstration.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]