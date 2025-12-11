# a simple util that uses nvidia-smi to monitor VRAM usage over time
# tracks the peak and average VRAM usage during the monitored period
import subprocess
import time


datapoints = []
start_time = time.time()
def monitor_vram(interval=10.0):
    while True:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,nounits,noheader'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print(f"Error querying VRAM: {result.stderr}")
            break
        vram_usage = int(result.stdout.strip().split('\n')[0])  # in MB
        datapoints.append(vram_usage)
        
        mean_vram = sum(datapoints) / len(datapoints)
        sorted_points = sorted(datapoints)
        p90_vram = sorted_points[int(0.9 * len(sorted_points)) - 1]
        p95_vram = sorted_points[int(0.95 * len(sorted_points)) - 1]
        peak_vram = max(datapoints)
        elapsed = time.time() - start_time
        print(f"[{elapsed:.1f}s] Current VRAM: {vram_usage} MB | Mean: {mean_vram:.1f} MB | P90: {p90_vram} MB | P95: {p95_vram} MB | Peak: {peak_vram} MB", end='\r')
        
        time.sleep(interval)
        
if __name__ == "__main__":
    print("Starting VRAM monitoring...")
    monitor_vram(interval=10.0)