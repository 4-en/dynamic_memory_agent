# defines and runs benchmarks for DMA system
# compare against baseline llm, llm with semantic search, and dma-augmented llm
import time
import json
import pathlib
import matplotlib.pyplot as plt

plt.style.use('seaborn-darkgrid')

from dma.config import DmaConfig, get_config
from dma.utils import get_data_dir
from dma.core import Conversation, Message
from dma.pipeline import Pipeline

from .benchmark_models import (BenchmarkKnowledgeBase, BenchmarkResult)

def run_benchmark(generator:callable, tasks:list) -> float:
    """Runs benchmark tasks using the provided generator function.
    
    Args:
        generator (callable): Function that takes a Conversation and returns a Message.
        
    Returns:
        float: Average accuracy across all tasks.
    """
    # TODO: implement benchmark logic
    
    return 0.0

def get_semantic_search_callable(pipeline:Pipeline) -> callable:
    """Returns a callable that runs semantic search using the pipeline."""
    def semantic_search_callable(conversation:Conversation) -> Message:
        
        retriever = pipeline.retriever
        if retriever is None:
            raise ValueError("Retriever is not set in the pipeline.")
        
        
        # TODO: implement basic semantic search logic
        
        
        return pipeline.generator.generate(conversation)
    return semantic_search_callable

def main():
    BENCHMARK_ID = f"benchmark_{int(time.time())}"
    BENCHMARK_DIR = get_data_dir() / "benchmarks" / BENCHMARK_ID

    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    
    # Define benchmark knowledge bases
    knowledge_bases = [
        BenchmarkKnowledgeBase(
            name="Wikipedia Solar System",
            description="Benchmark on questions about the solar system from Wikipedia.",
            categories=["Solar System"]
        )
    ]
    
    for kb in knowledge_bases:
        # 1. load knowledge base data
        
        # 2. define benchmark tasks
        
        # 3. build graph memory from knowledge base
        
        # 4. run benchmarks with different models
        
        MODELS = {
            "Qwen3-14B": {"hf_repo": "unsloth/Qwen3-14B-GGUF", "hf_file": "*Q4_K_M.gguf"},
            "Llama2-13B": {"hf_repo": "TheBloke/Llama-2-13B-Chat-GGUF", "hf_file": "*Q4_K_M.gguf"}
        }
        
        MODES = [
            "baseline",
            "semantic_search",
            "dma_augmented"
        ]
        
        # run each model + mode combination
        results = []
        config = get_config()
        for model in MODELS.keys():
            config.hf_repo = MODELS[model]["hf_repo"]
            config.hf_file = MODELS[model]["hf_file"]
            pipeline = Pipeline(config=config)
            for mode in MODES:
                name = f"{model}_{mode}"
                print(f"Running benchmark: {name}")
                
                f = None
                match mode:
                    case "baseline":
                        f = pipeline.generator.generate
                    case "semantic_search":
                        f = pipeline.run_semantic_search
                    case "dma_augmented":
                        f = pipeline.generate
                    case _:
                        raise ValueError(f"Unknown mode: {mode}")
                
            del pipeline # make sure to free up memory
        