import concurrent.futures
import time
from typing import Dict, List


def dummy_api_metric(model_url: str) -> dict:
    """Simulates a fast I/O-bound task, like an API call."""
    start_time = time.time()
    # print(f"Starting API metric for {model_url}...")
    time.sleep(0.5)  # Simulate a 500ms API response time
    end_time = time.time()
    elapsed_time = (end_time - start_time) * 1000  # Convert to milliseconds
    # print(f"Finished API metric for {model_url}
    # in {elapsed_time:.0f}ms.")
    return {
        "metric_name": "api_metric",
        "score": 0.8,
        "latency_ms": round(elapsed_time),
    }


def dummy_local_metric(model_url: str) -> dict:
    """Simulates a slow CPU-bound task, like a local analysis."""
    start_time = time.time()
    # print(f"Starting local metric for {model_url}...")
    time.sleep(2)  # Simulate a 2s local file analysis
    end_time = time.time()
    elapsed_time = (end_time - start_time) * 1000  # Convert to milliseconds
    # print(f"Finished local metric for {model_url} in {elapsed_time:.0f}ms.")
    return {
        "metric_name": "local_metric",
        "score": 0.9,
        "latency_ms": round(elapsed_time),
    }


def run_metrics_in_parallel(model_urls: List[str]) -> List[Dict]:
    """
    Runs dummy metrics for each model URL in parallel and prints the results.
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for url in model_urls:
            # Submit each dummy metric function to the executor
            futures.append(executor.submit(dummy_api_metric, url))
            futures.append(executor.submit(dummy_local_metric, url))

        # Wait for all futures to complete and collect the results
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    return results


if __name__ == "__main__":
    # dummy links
    model_list = [
        "https://huggingface.co/model1",
        "https://huggingface.co/model2",
    ]

    start_all = time.time()
    all_results = run_metrics_in_parallel(model_list)
    end_all = time.time()

    print("\n--- All Metrics Completed ---")
    for result in all_results:
        print(
            f"Metric: {result['metric_name']}, Score:",
            "{result['score']}, Latency: {result['latency_ms']}ms",
        )

    total_time = (end_all - start_all) * 1000
    print(f"\nTotal elapsed time for all models: {total_time:.0f}ms")
