import asyncio
import json
import os
import time
from collections import defaultdict
from typing import Dict, List

import pandas as pd
from tqdm import tqdm

from _client import MCPClient

current_dir = os.path.dirname(os.path.abspath(__file__))

# Define k values for recall and precision metrics
k_list = [1, 2, 5, 10]


def _calculate_metrics(
    gold_file_names: List[str], retrieved_file_names: List[str]
) -> Dict[str, Dict[int, float]]:
    """
    Calculate recall@k and precision@k metrics.

    Args:
        gold_file_names: List of ground truth file names
        retrieved_file_names: List of retrieved file names

    Returns:
        Dictionary containing recall and precision values at different k values
    """
    metrics = {"recall": {}, "precision": {}}

    for k in k_list:
        # Only consider top-k retrieved files
        top_k_retrieved = retrieved_file_names[:k]

        # Calculate recall@k = (number of relevant files in top-k) / (total number of relevant files)
        if len(gold_file_names) > 0:
            recall_k = sum(1 for f in top_k_retrieved if f in gold_file_names) / len(
                gold_file_names
            )
        else:
            recall_k = 0.0

        # Calculate precision@k = (number of relevant files in top-k) / k
        if k > 0:
            precision_k = sum(1 for f in top_k_retrieved if f in gold_file_names) / k
        else:
            precision_k = 0.0

        metrics["recall"][k] = round(recall_k, 4)
        metrics["precision"][k] = round(precision_k, 4)

    return metrics


def _print_metrics_line(metrics: Dict[int, float], metric_name: str, pre_str="", post_str="\n"):
    """
    Print metrics in a formatted line.

    Args:
        metrics: Dictionary containing metric values at different k values
        metric_name: Name of the metric (recall or precision)
        pre_str: String to print before metric values
        post_str: String to print after metric values
    """
    print(pre_str, end="")
    for k in k_list:
        print(f"{metric_name}@{k}: {metrics[k]:.3f} ", end="")
    print(post_str, end="")


async def evaluate(
    output_dir: str = "./eval_output",
    flag: str = "result",
    retry_num: int = 3,
    base_wait_time: int = 2,
):
    """
    Evaluate the retrieval performance on the test dataset.

    Args:
        output_dir: Directory for output files
        flag: Flag for the evaluation run
        retry_num: Number of retry attempts for retrieval
        base_wait_time: Base wait time between retries in seconds
    """
    server_script_path = os.path.join(
        current_dir, "../..", "mcp_pymilvus_code_generate_helper", "stdio_server.py"
    )
    if not os.path.exists(server_script_path):
        raise FileNotFoundError(f"Server script path not found: {server_script_path}")
    print(f"Server script path: {server_script_path}")
    # Create MCPClient
    mcp_client = MCPClient(
        server_script_path=server_script_path,
        model_name="claude-3-5-sonnet-20241022",
        max_tokens=1000,
    )
    await mcp_client.connect_to_server()

    # Download dataset
    from huggingface_hub import hf_hub_download

    file_path = hf_hub_download(
        repo_id="brcarry/milvus-sdk-code-helper-test-dataset",
        filename="test_dataset.json",
        repo_type="dataset",
    )

    # Create output directories
    eval_output_subdir = os.path.join(output_dir, flag)
    os.makedirs(eval_output_subdir, exist_ok=True)
    csv_file_path = os.path.join(eval_output_subdir, "details.csv")
    statistics_file_path = os.path.join(eval_output_subdir, "statistics.json")

    # Load test dataset
    with open(file_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # Initialize variables for resuming
    start_idx = 0
    existing_df = pd.DataFrame()
    existing_statistics = defaultdict(dict)
    total_error_num = 0
    total_sample_num = 0

    # Check if previous results exist
    if os.path.exists(csv_file_path):
        existing_df = pd.read_csv(csv_file_path)
        start_idx = len(existing_df)
        print(f"Loading results from {csv_file_path}, start_index = {start_idx}")

    if os.path.exists(statistics_file_path):
        with open(statistics_file_path, "r") as f:
            existing_statistics = json.load(f)
        print(
            f"Loading statistics from {statistics_file_path}, will recalculate statistics based on both new and existing results."
        )
        total_error_num = existing_statistics.get("error_num", 0)
        total_sample_num = existing_statistics.get("sample_num", 0)

    # Get items to process (for resuming)
    items = list(json_data.items())
    items_to_process = items[start_idx:]

    # Process each sample
    for idx, (query, gold_infos) in enumerate(tqdm(items_to_process)):
        global_idx = idx + start_idx
        gold_file_names = [gold_info["file_name"] for gold_info in gold_infos]

        # Retrieve files with retry mechanism
        retrieved_file_names = []
        error = False
        # for i in range(retry_num):
            # try:
        retrieved_file_names, tool_call_logs = await mcp_client.retrieve(
                query
            )  # TODO: we can handle tool_call_logs further
            #     break
            # except Exception as e:
            #     wait_time = base_wait_time * (2**i)
            #     print(
            #         f"Retrieval failed for query: {query}. Retry after {wait_time} seconds... Error: {e}"
            #     )
            #     time.sleep(wait_time)
            #     if i == retry_num - 1:
            #         error = True

        if error:
            total_error_num += 1
            print(
                f"Retrieval failed for query: {query} after {retry_num} retries. Current error count: {total_error_num}"
            )

        # Calculate metrics
        metrics = _calculate_metrics(gold_file_names, retrieved_file_names)

        # Print current sample results
        print(f"Sample {global_idx}: {query}")
        _print_metrics_line(metrics["recall"], "Recall", pre_str="Recall metrics: ")
        _print_metrics_line(metrics["precision"], "Precision", pre_str="Precision metrics: ")
        print(f"Gold file names: {gold_file_names}")
        print(f"Retrieved file names: {retrieved_file_names[:10]}")
        print("-" * 100)

        # Save current sample result
        current_result = [
            {
                "idx": global_idx,
                "query": query,
                "metrics": metrics,
                "gold_file_names": gold_file_names,
                "retrieved_file_names": retrieved_file_names,
                "error": error,
            }
        ]

        current_df = pd.DataFrame(current_result)
        existing_df = pd.concat([existing_df, current_df], ignore_index=True)
        existing_df.to_csv(csv_file_path, index=False)

        # Update statistics
        total_sample_num += 1

        # Calculate average metrics
        avg_recall = {k: 0.0 for k in k_list}
        avg_precision = {k: 0.0 for k in k_list}

        for k in k_list:
            recall_values = []
            precision_values = []

            for _, row in existing_df.iterrows():
                row_metrics = row["metrics"]
                if isinstance(row_metrics, str):
                    row_metrics = eval(row_metrics)

                recall_values.append(row_metrics["recall"][k])
                precision_values.append(row_metrics["precision"][k])

            avg_recall[k] = sum(recall_values) / len(recall_values)
            avg_precision[k] = sum(precision_values) / len(precision_values)

        # Update statistics
        existing_statistics["average_recall"] = avg_recall
        existing_statistics["average_precision"] = avg_precision
        existing_statistics["error_num"] = total_error_num
        existing_statistics["sample_num"] = total_sample_num
        existing_statistics["error_rate"] = (
            total_error_num / total_sample_num if total_sample_num > 0 else 0
        )

        # Print average metrics
        _print_metrics_line(avg_recall, "Avg Recall", pre_str="\nAverage recall metrics: ")
        _print_metrics_line(avg_precision, "Avg Precision", pre_str="Average precision metrics: ")
        print("\n")

        # Save statistics
        with open(statistics_file_path, "w") as f:
            json.dump(existing_statistics, f, indent=4)

    print("Evaluation completed and results saved.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate MCP retrieval performance.")
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./eval_output",
        help="Output directory for evaluation results",
    )
    parser.add_argument("--flag", type=str, default="result", help="Flag for the evaluation run")

    args = parser.parse_args()

    asyncio.run(evaluate(output_dir=args.output_dir, flag=args.flag))
