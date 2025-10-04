# Dynamic Learning Memory System for AI Agents

## Overview
This project is a proof-of-concept implementation of a **graph-based dynamic learning memory system** for LLM-based agents, designed with smaller, locally deployable models in mind.  

The system enables an agent to:
- Form structured memories from user interactions
- Retrieve relevant knowledge efficiently
- Update or prune stored information when necessary
- Produce responses grounded in verifiable sources

The goal is to improve accuracy, consistency, and transparency compared to stateless or RAG-only approaches, while remaining efficient on consumer-grade hardware.

---

## Installation
### Requirements
- NVIDIA GPU with CUDA support (for LLM inference)
- NVidia Container Toolkit and drivers installed
- GPU-enabled Docker runtime
- Docker and Docker Compose

### Setup
1. Clone the repository:
   ```bash
   git clone
    cd dynamic_memory_agent
    ```
2. Build using make:
   ```bash
   make build
   ```

### Run Agent
Start the agent with:
```bash
make up
```

### Build memory from data (optional)
To initialize the memory graph from a dataset (e.g., a game wiki):
```bash
make build_memory DATASET_PATH=path/to/dataset.jsonl
```

## Features
- **Graph-based memory storage** (Neo4j planned, pluggable backend)
- **Hybrid retrieval**: semantic similarity (FAISS or custom), recency, and usage importance
- **Update & pruning** to handle contradictions and stale information
- **Grounded generation** with provenance tracking
- **Interfaces**:
  - CLI (minimum)
  - Optional: web interface, graph visualisation, memory inspection
- **Debug modes** to inspect retrieved entries, metadata, and updates

---

## Research Objectives
1. Develop a structured, graph-based memory architecture with rich metadata
2. Implement adaptive retrieval combining similarity, recency, and usage importance
3. Design update and pruning strategies for accuracy and efficiency
4. Integrate memory into an LLM-based agent with CLI and optional UI
5. Evaluate against non-learning and RAG-only baselines

---

## Tech Stack
- **Languages/Frameworks:** Python, PyTorch, Hugging Face Transformers, llama.cpp
- **Memory Backend:** Neo4j (graph database)
- **Retrieval:** FAISS or lightweight custom search
- **Models:** Open-source LLMs (~7B–40B parameters)

---

## Evaluation
Planned evaluation includes:
- **Datasets:** public general knowledge + custom domain-specific (e.g., game wiki data)
- **Baselines:** non-learning agent, RAG-only agent
- **Metrics:** accuracy, consistency, latency, retrieval quality, memory growth

---

## License
This project is released under the **MIT License**.
