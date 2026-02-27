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


---

## Usage
While designed to be used as a library, it also includes a simple web-ui and can run as a standalone application via Docker. 
The provided Docker setup is not required, but it simplifies the setup for Neo4j and the Python environment. 
Note that this still initializes an empty Memory database. You probably want to initialize it via `python -m dma build-memory`.

To use a custom Neo4j instance, set the following environment variables or set them in the constructor of the Neo4jMemory class:

`NEO4J_URI`
`NEO4J_USER`
`NEO4J_PASSWORD`
`NEO4J_DATABASE`


### Installation (Standalone with Docker)

#### Requirements
- NVIDIA GPU with CUDA support (for LLM inference)
- NVIDIA Container Toolkit and drivers installed
- GPU-enabled Docker runtime
- Docker and Docker Compose

#### Setup
Clone the repository:
```bash
git clone
cd dynamic_memory_agent
```

Build using make:
```bash
make build
```

#### Run Web UI
Start the agent with:
```bash
make up
```

#### Stopping
To stop (without wiping the Neo4j container):
```bash
make stop
```

### As a library

```python
from dma.pipeline import Pipeline
from dma.core import Message, Conversation

pipe = Pipeline()

message = Message("What's the distance between Earth and Mars?")
conversation = Conversation([message])

response = pipe.generate(conversation)

print(response.message_text[:100]+"..." )
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

## Research Objectives and Questions
This project aims to design and implement a prototype that is capable of enhancing grounded, source-based generation for LLMs
running on consumer hardware. At its core, the system should provide functions that can
improve the accuracy and reliability of LLM-based systems, combined with a simple deployment process that makes it usable for consumers on their local machines. This will be
realized using a supporting graph-based memory system, capable of retrieving the most relevant information for a given context, and processing it to improve the underlying LLM’s
generated output. Unlike static systems, it will also include a self-feedback mechanism,
which can improve the relevance of future results.
The following research objectives and questions detail the specific goals and questions
this project seeks to address:

### RO1: System Design
To design a dynamic, graph-based memory architecture that supports continuous
knowledge updates and self-feedback loops.

### RO2: System Implementation
To implement this architecture as a modular, locally deployable Python library
prototype compatible with consumer-grade hardware.

### RO3: Evaluation
To evaluate the effectiveness of the system in terms of retrieval accuracy, hallucination
reduction, and transparency compared to stateless and RAG-only baselines.

### RQ1: Software Architecture
What is an effective software architecture for a graph-based dynamic memory system
that is designed to efficiently store, organize and retrieve knowledge extracted from a
knowledge base during live interactions?

### RQ2: Retrieval Strategy
How can a hybrid retrieval strategy that combines semantic similarity1, entity recognition, 
recency, and usage-based importance be implemented to optimize the relevance
and utility of retrieved context?

### RQ3: Dynamic Improvements
How can a knowledge based be updated and pruned to automatically and improve
future results?

### RQ4: Performance Improvements
To what extent does the implemented proof of concept improve accuracy, consistency,
and transparency compared to a non-learning baseline and a RAG-only baseline?

---

## Architecture Overview
The following sections give a brief overview about how the system is designed and implemented.
It illustrates the core retrieval loop and the most important technologies and dependencies.

### Dynamic Memory Pipeline
The core component of the proposed system is a modular pipeline that manages the various
stages of processing required to generate responses based on user prompts and conversation
history. The pipeline is responsible for setting up all default components and registering any
non-standard ones provided by the user. It provides an interface for generating responses
by allowing users to input prompts and conversation history, and returning the final generated response.

<img width="2588" height="752" alt="pipeline_overview" src="https://github.com/user-attachments/assets/09a1ca79-8caa-4744-b1b7-a9694eca83d5" />

Each component within the pipeline has a specific role, and they interact in a defined
sequence to achieve the desired functionality. The pipeline directs the flow of data between
components, controlling the overall process from input to output. While the components
are designed to work together seamlessly within the pipeline, they are also modular and can
be used independently or replaced with custom implementations as needed. In addition,
a custom pipeline could also be created by instantiating the individual components and
connecting them manually, allowing for greater flexibility and customization.


### Tech Stack

- **Languages/Frameworks:** Python, PyTorch, Hugging Face Transformers, Sentence-Transformersm spaCy, llama.cpp, DeepEval
- **Memory Backend:** Neo4j (as graph and vector database)
- **Models:** Open-source LLMs compatible with llama.cpp (~7B–40B parameters, Qwen3)
- **Web UI API:** FastAPI

---

## Evaluation
The system was evaluated as a whole. Therefore, it is difficult to isolate the impact of
individual components on the overall performance. Most parameters and settings were
not optimized, as this would have required substantial experimentation and benchmarking,
which was beyond the scope of this due to time and financial constraints. However, the
benchmarks provide a comprehensive view of the system's capabilities and design. While not
representing the best result possible, they can be seen as a baseline for future improvements
and optimizations.


### Metrics
The benchmarks use DeepEval and LLM-as-a-Judge metrics to evaluate answers using different metrics. 
The questions/scenarios are based on the generated knowledgebase the systems are using, ensuring that every question is answerable using the available context.

These metrics include:

- **Correctness**: Measures whether the answer provided by the system is factually
correct compared to the expected answer.
- **Answer Relevancy**: Measures whether the answer is relevant to the user's ques-
tion, indicating that the system understood the prompt correctly and didn't include
unnecessary information.
- **Faithfulness**: Measures whether the answer is supported by the retrieved memories,
indicating that the system is using the provided context appropriately.
- **Hallucination**: Measures the frequency of unsupported or fabricated information in
the system's responses, indicating how often the model generates content not grounded
in the memory.

### Results
TODO

---

## License
This project is released under the **MIT License**.
