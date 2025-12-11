from dma.utils import get_data_dir, get_cache_dir
import os
import json

benchmark_data_dir = get_data_dir() / "benchmark-results"
os.makedirs(benchmark_data_dir, exist_ok=True)

def parse_log_to_results(log_path: str) -> dict:
    results = {}
    with open(log_path, "r") as f:
        lines = f.readlines()
        model_name = "UNKNOWN_MODEL"
        for line in lines:
            if "Testing Model:" in line:
                model_name_tmp = line.split(":")[1]
                model_name = model_name_tmp.replace("---", "").strip()
                continue
            if line.startswith("Metric:"):
                # parse format "Metric: <metric_name>, Score: <score_value>"
                parts = line.split(",")
                metric_name = parts[0].split(":")[1].strip()
                score_value = float(parts[1].split(":")[1].strip())
                if model_name not in results:
                    results[model_name] = {}
                if metric_name not in results[model_name]:
                    results[model_name][metric_name] = []
                results[model_name][metric_name].append(score_value)
                
    # average the scores for each metric
    THRESHOLD = 0.6
    for model_name, metrics in results.items():
        tmp_dict = metrics.copy()
        for metric_name, scores in metrics.items():
            average_score = sum(scores) / len(scores) if scores else 0
            tmp_dict[metric_name+"_average"] = average_score
            # also compute thresholded average
            thresholded_scores = [1 if score >= THRESHOLD else 0 for score in scores]
            thresholded_average = sum(thresholded_scores) / len(thresholded_scores) if thresholded_scores else 0
            tmp_dict[metric_name + "_thresholded"] = thresholded_average
            
            print(f"Model: {model_name}, Metric: {metric_name}, Average Score: {average_score:.2f}, Thresholded Average (>{THRESHOLD}): {thresholded_average:.2f}")
        results[model_name] = tmp_dict
    return results

import matplotlib.pyplot as plt

def dict_to_bar_chart(data: dict, output_path: str, title: str="Benchmark Results", subtitle: str=""):
    if "results" in data:
        data = data["results"]
        
    models = list(data.keys())
    all_metrics = list(next(iter(data.values())).keys())
    
    x = range(len(models))
    total_width = 0.8
    filters = ["_thresholded", "turns"]
    blacklist = ["contextual_recall"]
    
    norm_filters = ["turns"] # normalize values for these metrics to [0,1]
    
    # normalize metrics if needed
    for metric in all_metrics:
        if any(f in metric for f in norm_filters):
            # find max value across all models for this metric
            max_value = max(data[model][metric] for model in models)
            if max_value > 0:
                for model in models:
                    data[model][metric] /= max_value
    
    # 1. Filter metrics first
    valid_metrics = [m for m in all_metrics if any(f in m for f in filters) and not any(b in m for b in blacklist)]
    num_metrics = len(valid_metrics)
    
    if num_metrics == 0:
        print("No metrics found matching the filters.")
        return

    bar_width = total_width / num_metrics
    
    plt.style.use('ggplot')
    plt.figure(figsize=(12, 7)) # Increased size slightly to accommodate text
    
    # Track max score to adjust Y-axis later
    max_score = 0
    
    # fix: set faithfulness to 0 Baseline, since its always reported as 1.0
    for model in models:
        if "Baseline" in model and not "RAG" in model:
            for metric in valid_metrics:
                if "faithfulness" in metric:
                    data[model][metric] = 0.0
    
    for i, metric in enumerate(valid_metrics):
        scores = [data[model][metric] for model in models]
        
        # Update max_score for y-limit calculation
        current_max = max(scores) if scores else 0
        if current_max > max_score:
            max_score = current_max
        
        # Calculate centered positions
        bar_positions = [p - (total_width / 2) + (i * bar_width) + (bar_width / 2) for p in x]
        
        metric_label = metric.replace("_average", "").replace("_thresholded", "").replace("_", " ").title()
        
        # if normalized, add note
        if any(f in metric for f in norm_filters):
            metric_label += " (Normalized)"
        
        # 2. Capture the bar container to add labels
        rects = plt.bar(bar_positions, scores, width=bar_width, label=metric_label)
        
        # 3. Add the value labels on top
        # fmt='%.2f' rounds to 2 decimal places. Change to '%.1f' or '%d' if preferred.
        plt.bar_label(rects, padding=3, fmt='%.2f', fontsize=9)
        
    #clean_model_names = [model.split("_")[0] for model in models]
    clean_model_names = [model.split("_")[0] + " N" + model.split("_")[1] for model in models]
    
    plt.xlabel('Models')
    plt.ylabel('Scores')
    plt.title(title + ("\n" + subtitle if subtitle else ""))
    
    # Set Y-limit to give space for the labels on top
    plt.ylim(0, max_score * 1.15)
    
    plt.xticks(x, clean_model_names)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    # plt.show()
    plt.close()

def parse_main():
    import time
    log_file_path = benchmark_data_dir / "14b.txt"
    results = parse_log_to_results(log_file_path)
    
    # save results to json
    output_path = benchmark_data_dir / f"parsed_benchmark_results_14b.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)
    
    print(f"Parsed benchmark results saved to {output_path}.")
    
def plot_main():
    model_name = "unsloth/Qwen3-8B-GGUF_Q4_K_M"
    title = "Benchmark Results for " + model_name
    subtitle = "Wikipedia Solarsystem Category QA"
    output_chart_path = benchmark_data_dir / f"learning_benchmark_results_chart_{model_name.replace('/', '_')}.png"
    
    json_path = benchmark_data_dir / "learning_benchmark_20251210-044610.json"
    with open(json_path, "r") as f:
        results = json.load(f)
    
    dict_to_bar_chart(results, output_chart_path, title=title, subtitle=subtitle)
    print(f"Benchmark results chart saved to {output_chart_path}.")
    
if __name__ == "__main__":
    plot_main()
    #parse_main()