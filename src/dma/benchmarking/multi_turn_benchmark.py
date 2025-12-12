from dma.benchmarking.deep_eval_models import DynMemLLM, BaselineLLM, BaselineRAGLLM
from dma.benchmarking.benchmarks import SingleTurnBenchmark, MultiTurnBenchmark
from deepeval.dataset import ConversationalGolden

from dma.utils import get_data_dir, get_env_variable, get_cache_dir
from dma.pipeline import Pipeline
import os
import random

from deepeval.evaluate.types import EvaluationResult

USE_CACHE = True
OPENAI_API_KEY = get_env_variable("OPENAI_API_KEY")
if OPENAI_API_KEY is None:
    raise ValueError("OPENAI_API_KEY environment variable not set. Please set it in your .env file.")

benchmark_data_dir = get_data_dir() / "benchmark_data"

# get all text files in the benchmark data directory
document_paths = []
for file_name in os.listdir(benchmark_data_dir):
    if file_name.endswith(".txt"):
        document_paths.append(str(benchmark_data_dir / file_name))

# limit to first 10 documents for testing
random.seed(420)
document_paths = random.sample(document_paths, k=20)

# create the pipeline
pipeline = Pipeline()

model_name = "unsloth/Qwen3-8B-GGUF_Q4_K_M"
#model_name = "unsloth/Qwen3-14B-GGUF_Q4_K_M"

dyn_mem_llm = DynMemLLM(model_name=model_name, pipeline=pipeline)
baseline_llm = BaselineLLM(model_name=model_name, pipeline=pipeline)
baseline_rag_llm = BaselineRAGLLM(model_name=model_name, pipeline=pipeline)

# rebuild clean memory
from dma.extraction import build_memory_of_type
CATEGORIES = ["Solar System"]
print("Rebuilding memory before training/evaluation...")
#build_memory_of_type("wikipedia", category=",".join(CATEGORIES), remove_existing=True)
print("Memory rebuild complete.")


multi_turn_benchmark = MultiTurnBenchmark(document_paths=document_paths)

cache_dir = get_cache_dir() / "benchmarks" / "multi_turn_goldens"
found_cached = False
if USE_CACHE:
    # try to load cached goldens
    if cache_dir.exists():
        multi_turn_benchmark.scenarios = []
        for file_name in os.listdir(cache_dir):
            if file_name.startswith("golden_") and file_name.endswith(".json"):
                golden_path = cache_dir / file_name
                with open(golden_path, "r") as f:
                    golden_json = f.read()
                    golden = ConversationalGolden.model_validate_json(golden_json)
                    multi_turn_benchmark.scenarios.append(golden)
        print(f"Loaded {len(multi_turn_benchmark.scenarios)} cached goldens from {cache_dir}.")
        if len(multi_turn_benchmark.scenarios) > 0:
            found_cached = True

if not found_cached or not USE_CACHE:
    multi_turn_benchmark.generate_scenarios(num_scenarios=2)
    # save goldens for caching

    os.makedirs(cache_dir, exist_ok=True)
    for i, golden in enumerate(multi_turn_benchmark.scenarios):
        golden_path = cache_dir / f"golden_{i}.json"
        with open(golden_path, "w") as f:
            f.write(golden.model_dump_json())


multi_turn_benchmark.scenarios = random.sample(multi_turn_benchmark.scenarios, k=7)  # limit to first 5 for testing
llms = [baseline_rag_llm, dyn_mem_llm, baseline_llm]
multi_turn_results = multi_turn_benchmark.run(llms=llms)

# output results
for model_name, results in multi_turn_results.items():
    print(f"\n=== Results for {model_name} ===")
    avg_scores = {}
    for name, scores in results.items():
        if name == "test_cases":
            continue
        if not isinstance(scores, list):
            continue
        if len(scores) == 0:
            continue
        if not all(isinstance(score, (int, float)) for score in scores):
            continue
        average_score = sum(scores) / len(scores) if scores else 0
        print(f"{name}: Average Score = {average_score:.2f} over {len(scores)} cases")
        avg_scores[name+"_average"] = average_score
        
        thresholded_scores = [1 if score >= 0.6 else 0 for score in scores]
        thresholded_average = sum(thresholded_scores) / len(thresholded_scores) if thresholded_scores else 0
        print(f"{name}: Thresholded Average Score (>=0.6) = {thresholded_average:.2f} over {len(thresholded_scores)} cases")
        avg_scores[name+"_thresholded_average"] = thresholded_average
        
        
    for avg_name, avg_score in avg_scores.items():
        multi_turn_results[model_name][avg_name] = avg_score
        
# save as json
import json
import time

qa_and_results = {
    "goldens": [golden.model_dump(mode="json") for golden in multi_turn_benchmark.scenarios],
    "results": multi_turn_results
}

timestamp = time.strftime("%Y%m%d-%H%M%S")
output_file = f"multi_turn_results_{timestamp}.json"
dir_path = get_data_dir() / "benchmark-results"
os.makedirs(dir_path, exist_ok=True)
output_file = dir_path / output_file
with open(output_file, "w") as f:
    json.dump(qa_and_results, f, indent=4)