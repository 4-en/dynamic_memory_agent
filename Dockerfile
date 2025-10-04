# === STAGE 1: BUILDER (Heavy lifting and compilation) ===
# TODO: Uncomment the builder stage and copy from it to reduce final image size
# for actual deployment, if needed.
#FROM nvidia/cuda:13.0.1-devel-ubuntu24.04 AS builder
FROM nvidia/cuda:13.0.1-devel-ubuntu24.04

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

# 1. Install Python 3, pip, and other necessary build dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        # Add 'build-essential' or any other non-Python dependencies required for your package
        # e.g., git, libatlas-base-dev
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${APP_HOME}


COPY pyproject.toml ./
COPY src/ ./src/
COPY README.md .
COPY LICENSE .
COPY config.cfg .


#RUN python3 -m pip install . --no-deps --no-build-isolation --break-system-packages --timeout 600

# GGML_CUDA=on for llama-cpp-python with CUDA support
ENV GGML_CUDA=on

# Re-install with the source code present. All heavy dependencies are already cached.
RUN python3 -m pip install . --break-system-packages --timeout 600


# === STAGE 2: FINAL (Smallest possible runtime image) ===
# Switch to the smaller runtime image. It only has libraries, no development tools.
#FROM nvidia/cuda:13.0.1-runtime-ubuntu24.04 AS final

ENV APP_HOME=/app

# Create a non-root user for security (best practice)
RUN groupadd --system appuser && useradd --system -g appuser appuser
# Make the application directory and set correct permissions
#RUN mkdir ${APP_HOME} && chown -R appuser:appuser ${APP_HOME}
RUN chown -R appuser:appuser ${APP_HOME}
WORKDIR ${APP_HOME}

# Copy the application code and *installed packages* from the builder stage
# /usr/local/lib/python3.12/site-packages is the standard location for pip install in Ubuntu
#COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
#COPY --from=builder ${APP_HOME} ${APP_HOME}
# Copy the Spacy model data, which is in a different location
#COPY --from=builder /usr/local/lib/python3.12/site-packages/en_core_web_sm/ /usr/local/lib/python3.12/site-packages/en_core_web_sm/

# Download Spacy model
RUN python3 -m spacy download en_core_web_sm --break-system-packages --timeout 600

# Set the final user to run the application (security)
USER appuser

# Default: run package as a module
CMD ["python3", "-m", "dma"]