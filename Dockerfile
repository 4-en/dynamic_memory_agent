# syntax=docker/dockerfile:1

########## CUDA PATH ##########
FROM nvidia/cuda:13.0.1-devel-ubuntu24.04 AS builder-cuda

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 APP_HOME=/app
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3.12 python3-pip build-essential cmake git && \
    rm -rf /var/lib/apt/lists/*
WORKDIR ${APP_HOME}

# Copy sources
COPY pyproject.toml ./
COPY src/ ./src/
COPY README.md .
COPY LICENSE .
COPY config.cfg .

# Enable CUDA in ggml
ENV CMAKE_ARGS="CMAKE_BUILD_PARALLEL_LEVEL=8"

ENV CMAKE_ARGS="-DGGML_CUDA=ON \
 -DLLAMA_BUILD_EXAMPLES=OFF \
 -DLLAMA_BUILD_TESTS=OFF \
 -DLLAMA_BUILD_SERVER=OFF \
 -DLLAMA_BUILD_TOOLS=OFF \
 -DCMAKE_CUDA_ARCHITECTURES=86\;89\;90\;110\;120"

# ENV CMAKE_EXE_LINKER_FLAGS="-Wl,-rpath-link,/usr/local/cuda/targets/x86_64-linux/lib/stubs -L/usr/local/cuda/targets/x86_64-linux/lib/stubs -lcuda"
# (optional but often helpful)
#ENV CMAKE_SHARED_LINKER_FLAGS="-Wl,-rpath-link,/usr/local/cuda/targets/x86_64-linux/lib/stubs"


RUN python3 -m pip install . --no-cache-dir --timeout 600 --break-system-packages

FROM nvidia/cuda:13.0.1-runtime-ubuntu24.04 AS final-cuda
ENV APP_HOME=/app
RUN groupadd --system appuser && useradd --system -g appuser appuser
WORKDIR ${APP_HOME}
COPY --from=builder-cuda /usr/local/lib/python*/dist-packages/ /usr/local/lib/python*/dist-packages/
COPY --from=builder-cuda /usr/local/lib/python*/site-packages/ /usr/local/lib/python*/site-packages/
COPY --from=builder-cuda ${APP_HOME} ${APP_HOME}
RUN python3 -m pip install spacy --no-cache-dir --break-system-packages && python3 -m spacy download en_core_web_sm --break-system-packages
USER appuser
CMD ["python3", "-m", "dma"]

########## CPU PATH ##########
FROM ubuntu:24.04 AS final-cpu

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 APP_HOME=/app
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3.12 python3-pip build-essential cmake git && \
    rm -rf /var/lib/apt/lists/*
WORKDIR ${APP_HOME}

COPY pyproject.toml ./
COPY src/ ./src/
COPY README.md .
COPY LICENSE .
COPY config.cfg .

# Disable CUDA in ggml
ENV CMAKE_ARGS="-DGGML_CUDA=OFF" CMAKE_BUILD_PARALLEL_LEVEL=8
RUN python3 -m pip install . --no-cache-dir --timeout 600 --break-system-packages

#FROM ubuntu:24.04 AS final-cpu
#ENV APP_HOME=/app
#RUN groupadd --system appuser && useradd --system -g appuser appuser
#WORKDIR ${APP_HOME}
#COPY --from=builder-cpu /usr/local/bin/python3* /usr/local/bin/
#COPY --from=builder-cpu /usr/local/lib/python*/dist-packages/ /usr/local/lib/python*/dist-packages/
#COPY --from=builder-cpu /usr/local/lib/python*/site-packages/ /usr/local/lib/python*/site-packages/
#COPY --from=builder-cpu ${APP_HOME} ${APP_HOME}


#RUN python3 -m pip install spacy --no-cache-dir --break-system-packages && python3 -m spacy download en_core_web_sm --break-system-packages
RUN python3 -m spacy download en_core_web_sm --break-system-packages
USER appuser
CMD ["python3", "-m", "dma"]
