# Dynamic Learning Memory System for AI Agents

Large Language Model (LLM)-based systems have demonstrated remarkable progress in
natural language understanding and generation, yet their ability to learn and adapt during
live operation remains severely limited. Most current systems operate without a persistent
memory, preventing them from refining knowledge or improving behaviour over time. Instead,
they are trained in a completely separate step, requiring often millions of training steps to adjust
their weights, which in turn require powerful server clusters to operate. While approaches like
Retrieval-Augmented Generation (RAG) or more advanced graph-based techniques exist, they
can still suffer from a lack of transparency, efficient retrieval or sufficient flexibility.

Building on the concept of RAG and other graph-based augmentation techniques, this thesis
proposes a dynamic learning memory as the core knowledge base for LLM applications. Using
a hybrid retrieval approach that utilizes both semantic similarity and Named-entity recognition
(NER), this system transforms an existing static knowledge base into a dynamic memory, which
adjusts itself over time, based on a self-feedback mechanism and the corresponding ranking and
filtering algorithm.

The modular pipeline can be used as a library to enable agentic and natural language use
cases that target local or consumer-oriented systems. It serves as a simple and ready to use
library that can build a memory based on an existing knowledge base and use it to generate
grounded and source-based responses. The modules can also be used separately, making the
system highly customizable. The library also comes with a basic web interface, that can be
used to run the pipeline on local networks as a chat assistant. It shows improvements over non-
learning and RAG-only baselines in various benchmarks, while operating within the constraints
of consumer-grade hardware.

## Overview
This project is a proof-of-concept implementation of a **graph-based dynamic learning memory system** for LLM-based agents, designed with smaller, locally deployable models in mind.  

The system enables an agent to:
- Build a graph memory using an existing knowledge base
- Retrieve relevant knowledge efficiently using hybrid retrieval
- Update or prune stored information when necessary
- Produce responses grounded in verifiable sources

The goal is to improve accuracy, consistency, and transparency compared to stateless or RAG-only approaches, while remaining efficient on consumer-grade hardware.

While designed to be used as a library, it also includes a simple web-ui and can run as a standalone application via Docker.

---

## Installation (Standalone with Docker)
### Requirements
- NVIDIA GPU with CUDA support (for LLM inference)
- NVIDIA Container Toolkit and drivers installed
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

### Run Web UI
Start the agent with:
```bash
make up
```

### Stopping
To stop (without wiping the Neo4j container):
```bash
make stop
```

## Features
- **Graph-based memory storage** (Neo4j)
- **Hybrid retrieval**: semantic similarity and entity-based searched, with recency, and feedback data for ranking
- **Update & pruning** to prioritize relevant information and improve future retrieval results
- **Grounded generation** with source tracking
- **Interfaces**:
  - CLI
  - Basic web ui

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
- **Models:** Open-source LLMs compatible with llama.cpp (~7B–40B parameters, Qwen3)
- **Web UI API:** FastAPI

---

## Evaluation
Planned evaluation with LLM-as-a-judge includes:
- **Datasets:** custom domain-specific (e.g., game wiki data)
- **Baselines:** non-learning agent, RAG-only agent, pure LLM
- **Metrics:** correctness, faithfulness, halucination

---

## License
This project is released under the **MIT License**.
