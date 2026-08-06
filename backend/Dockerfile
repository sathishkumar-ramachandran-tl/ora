# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Install system dependencies required for psycopg (PostgreSQL) if not binary, 
# but mostly for general stability.
# libpq-dev is often needed for building psycopg from source, though binary wheel avoids this.
# We'll stick to a simple slim install.

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Run the web service on container startup. Agent state is checkpointed to Postgres
# (see app/agents/checkpointer.py), not held in-process, so it's safe to run multiple
# worker processes — size this to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
CMD exec gunicorn --bind :$PORT --workers 4 --threads 8 --timeout 0 run:app
