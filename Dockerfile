# Minimal PyTorch + CUDA runtime base
FROM pytorch/pytorch:2.8.0-cuda12.9-cudnn9-runtime

# Keep Python output unbuffered and pip lean
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy metadata + source (src/ layout) and install package
COPY pyproject.toml ./
COPY src/ ./src/

# Install package (editable install for faster inner-loop dev)
RUN python -m pip install -U pip && \
    pip install -e .

# Default: run package as a module
CMD ["python", "-m", "dma"]

