from dma.benchmarking.deep_eval_models import DynMemLLM, BaselineLLM, BaselineRAGLLM
from dma.benchmarking.benchmarks import SingleTurnBenchmark, MultiTurnBenchmark
from deepeval.dataset import Golden

from dma.utils import get_data_dir, get_env_variable, get_cache_dir
from dma.pipeline import Pipeline
import os

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
document_paths = document_paths[:50]

# create the pipeline
pipeline = Pipeline()

model_name = "unsloth/Qwen3-8B-GGUF_Q4_K_M"
#model_name = "unsloth/Qwen3-14B-GGUF_Q4_K_M"

dyn_mem_llm = DynMemLLM(model_name=model_name, pipeline=pipeline)
baseline_llm = BaselineLLM(model_name=model_name, pipeline=pipeline)
baseline_rag_llm = BaselineRAGLLM(model_name=model_name, pipeline=pipeline)

single_turn_benchmark = SingleTurnBenchmark(document_paths=document_paths)
cache_dir = get_cache_dir() / "benchmarks" / "single_turn_goldens"
found_cached = False
if USE_CACHE:
    # try to load cached goldens
    if cache_dir.exists():
        single_turn_benchmark.goldens = []
        for file_name in os.listdir(cache_dir):
            if file_name.startswith("golden_") and file_name.endswith(".json"):
                golden_path = cache_dir / file_name
                with open(golden_path, "r") as f:
                    golden_json = f.read()
                    golden = Golden.model_validate_json(golden_json)
                    single_turn_benchmark.goldens.append(golden)
        print(f"Loaded {len(single_turn_benchmark.goldens)} cached goldens from {cache_dir}.")
        if len(single_turn_benchmark.goldens) > 0:
            found_cached = True

if not found_cached or not USE_CACHE:
    single_turn_benchmark.generate_test_data(num_questions=2)

    # save goldens for caching

    os.makedirs(cache_dir, exist_ok=True)
    for i, golden in enumerate(single_turn_benchmark.goldens):
        golden_path = cache_dir / f"golden_{i}.json"
        with open(golden_path, "w") as f:
            f.write(golden.model_dump_json())

import random
random.seed(420)
single_turn_benchmark.goldens = random.sample(single_turn_benchmark.goldens, 23)  # limit to first 3 for testing
llms = [dyn_mem_llm]
single_turn_results = single_turn_benchmark.run(llms=llms)

# output results
for model_name, results in single_turn_results.items():
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
        single_turn_results[model_name][avg_name] = avg_score
        
# save as json
import json
import time

qa_and_results = {
    "goldens": [golden.model_dump(mode="json") for golden in single_turn_benchmark.goldens],
    "results": single_turn_results
}

timestamp = time.strftime("%Y%m%d-%H%M%S")
output_file = f"single_turn_results_{timestamp}.json"
dir_path = get_data_dir() / "benchmark-results"
os.makedirs(dir_path, exist_ok=True)
output_file = dir_path / output_file
with open(output_file, "w") as f:
    json.dump(qa_and_results, f, indent=4)