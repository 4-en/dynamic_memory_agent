# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS runtime

# ---- System setup ----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build essentials only if your deps need them (e.g. for psycopg2, lxml).
# Keep minimal for smaller images.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

# ---- App setup ----
WORKDIR /app

# Copy only files needed to resolve dependencies first (better layer caching)
# If you also have a lock file (e.g. poetry.lock/uv.lock/requirements.lock), copy it here too.
COPY pyproject.toml ./

# If your build backend needs extra files (e.g. README.md, LICENSE used in wheel metadata),
# uncomment and copy them too:
# COPY README.md LICENSE ./

# Upgrade pip & build, then install your project (PEP 517/518 build from pyproject)
RUN python -m pip install --upgrade pip build \
 && python -m pip install .

# Now copy the rest of the project (source, configs, etc.)
COPY . .

# (Optional) create a non-root user for better security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose your app port if it has one (optional)
# EXPOSE 3000

# ---- Entrypoint ----
# You asked for an explicit entrypoint to your __main__.py.
# If your package is importable (src layout), using `-m dynamic_memory_agent` is even cleaner.
# Keeping your requested path:
ENTRYPOINT ["python", "./src/dynamic_memory_agent/__main__.py"]

# Optionally allow args via CMD (can be overridden by `docker run ... -- <args>`)
CMD []
