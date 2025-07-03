import os
import pandas as pd
from openai import OpenAI
import sys
from pathlib import Path

# Add the parent directory to import the retry decorator
sys.path.append(str(Path(__file__).parent.parent.parent / "mcp_pymilvus_code_generate_helper"))
from retry_decorator import openai_retry

@openai_retry
def _create_embedding_with_retry(client, content):
    """
    Create embedding with retry logic for a single piece of content.
    """
    response = client.embeddings.create(model="text-embedding-3-small", input=content)
    return response.data[0].embedding


def generate_embeddings(docs_dir_path, save_file_name):
    """
    Generate embeddings for markdown files in the specified directory.
    
    Args:
        docs_dir_path: Path to the directory containing markdown files
        save_file_name: Name of the output CSV file
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    markdown_files = []
    for root, dirs, files in os.walk(docs_dir_path):
        for file in files:
            if file.endswith(".md"):
                markdown_files.append(os.path.join(root, file))

    print(f"Found {len(markdown_files)} Markdown files to process")

    df = pd.DataFrame(columns=["metadata", "content", "embedding", "file_name"])
    processed_count = 0

    for file_index, markdown_path in enumerate(markdown_files):
        print(f"Processing file [{file_index + 1}/{len(markdown_files)}]: {markdown_path}")
        file_name = os.path.basename(markdown_path)

        try:
            with open(markdown_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Failed to read file: {e}")
            continue

        print(f"Content length: {len(content)} characters")

        try:
            print("Generating embedding...")
            embedding = _create_embedding_with_retry(client, content)
            print(f"Generation successful! Embedding dimension: {len(embedding)}")

            df.loc[len(df)] = {
                "metadata": "",
                "content": content,
                "embedding": embedding,
                "file_name": file_name,
            }

            processed_count += 1

            if processed_count % 10 == 0:
                temp_path = "embeddings_temp.csv"
                df.to_csv(temp_path, index=False)
                print(
                    f"Saved temporary results to: {temp_path}, processed {processed_count} documents so far"
                )

        except Exception as e:
            print(f"Failed to generate embedding after all retries: {e}")

    print("All documents process finished.")

    df.to_csv(save_file_name, index=False)

    print(f"Successfully generated embeddings and saved to: {save_file_name}")
    print(f"Dataset size: {len(df)} rows x {len(df.columns)} columns")
    
    return save_file_name

if __name__ == "__main__":
    # Example usage
    docs_dir_path = "/Users/zilliz/Downloads/web-content-master/API_Reference/pymilvus/v2.5.x/MilvusClient"
    save_file_name = "MilvusClient.csv"
    generate_embeddings(docs_dir_path, save_file_name)
