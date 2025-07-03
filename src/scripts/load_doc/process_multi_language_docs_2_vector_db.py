import argparse
import os
from typing import Dict, List, Optional
import sys
from pathlib import Path

import pandas as pd
import tiktoken
from openai import OpenAI
from pymilvus import DataType, Function, FunctionType, MilvusClient

# Add the parent directory to import the retry decorator
sys.path.append(str(Path(__file__).parent.parent.parent / "mcp_pymilvus_code_generate_helper"))
from retry_decorator import openai_retry


class MultiLangDocsProcessor:
    def __init__(self, base_dirs: Dict[str, str]):
        self.base_dirs = base_dirs
        self.folder_mapping = {
            "python": {"collections": "Collections", "partitions": "Partitions"},
            "node": {"collections": "Collections", "partitions": "Partitions"},
            "java": {"collections": "Collections", "partitions": "Partitions"},
            "go": {"collections": "Collection", "partitions": "Partition"},
            "csharp": {"collections": "Collection", "partitions": "Partition"},
            "restful": {"collections": "Collection (v2)", "partitions": "Partition (v2)"},
        }

        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.max_tokens = 8192  # OpenAI embedding model token limit

    def truncate_content(self, content: str) -> str:
        """Truncate content to fit token limit"""
        tokens = self.encoding.encode(content)
        if len(tokens) > self.max_tokens:
            truncated_tokens = tokens[: self.max_tokens]
            return self.encoding.decode(truncated_tokens)
        return content

    @openai_retry
    def _create_embedding_with_retry(self, content: str) -> List[float]:
        """Create embedding with retry logic for a single piece of content."""
        response = self.client.embeddings.create(
            model="text-embedding-3-small", input=content
        )
        return response.data[0].embedding

    def generate_embedding(self, content: str) -> Optional[List[float]]:
        """Generate embedding for text"""
        try:
            truncated_content = self.truncate_content(content)
            return self._create_embedding_with_retry(truncated_content)
        except Exception as e:
            print(f"Error generating embedding after all retries: {e}")
            return None

    def normalize_filename(self, python_filename: str, target_lang: str) -> str:
        """Convert Python filename format to target language format"""
        base_name = os.path.splitext(python_filename)[0]
        words = base_name.split("_")

        if target_lang == "python":
            return python_filename
        elif target_lang in ["node", "java"]:
            return words[0].lower() + "".join(word.capitalize() for word in words[1:]) + ".md"
        elif target_lang in ["go", "csharp"]:
            result = "".join(word.capitalize() for word in words) + ".md"
            if target_lang == "csharp":
                result = result.replace(".md", "Async().md")
            return result
        elif target_lang == "restful":
            return " ".join(word.upper() for word in words) + ".md"
        return python_filename

    def find_matching_files(self, python_file: str) -> Dict[str, str]:
        """Find corresponding files in other languages based on Python file path"""
        matches = {"python": python_file}

        parts = python_file.split("/")
        category = parts[-2]  # Collections or Partitions
        filename = os.path.basename(python_file)

        for lang, base_dir in self.base_dirs.items():
            if lang == "python":
                continue

            lang_category = self.folder_mapping[lang].get(category.lower(), category)

            if lang == "restful" and lang_category == category:
                lang_category += " (v2)"

            target_filename = self.normalize_filename(filename, lang)
            target_path = os.path.join(base_dir, lang_category, target_filename)

            if os.path.exists(target_path):
                matches[lang] = target_path
            else:
                original_path = os.path.join(base_dir, category, target_filename)
                if os.path.exists(original_path):
                    matches[lang] = original_path
                else:
                    matches[lang] = None

        return matches

    def read_file_content(self, file_path: Optional[str]) -> str:
        """Read file content, return empty string if file doesn't exist"""
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
        return ""

    def process_docs(self, output_file: str):
        """Process all documents and generate CSV file"""
        data = []
        embedding_errors = 0

        for root, _, files in os.walk(self.base_dirs["python"]):
            for file in files:
                if file.endswith(".md"):
                    python_file = os.path.join(root, file)
                    matches = self.find_matching_files(python_file)

                    contents = {
                        lang: self.read_file_content(path) for lang, path in matches.items()
                    }

                    python_content = contents.get("python", "")
                    embedding = self.generate_embedding(python_content)
                    if embedding is None:
                        embedding_errors += 1

                    row = {
                        **{f"{lang}_path": path for lang, path in matches.items()},
                        **{f"{lang}_content": content for lang, content in contents.items()},
                        "embedding": embedding,
                    }
                    data.append(row)

        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        print(f"Successfully processed {len(data)} documents and saved to {output_file}")

        print("\nDocument matching statistics:")
        print("-" * 50)
        print(f"Total Python documents: {len(data)}")
        for lang in self.base_dirs.keys():
            matched_count = df[f"{lang}_path"].notna().sum()
            print(
                f"{lang} matched count: {matched_count} (match rate: {matched_count / len(data) * 100:.2f}%)"
            )
        print(
            f"Embedding generation failures: {embedding_errors} (failure rate: {embedding_errors / len(data) * 100:.2f}%)"
        )
        print("-" * 50)


def create_milvus_client(uri: str, token: str) -> MilvusClient:
    """Create Milvus client"""
    print(f"Connecting to Milvus server: {uri}")
    client = MilvusClient(uri=uri, token=token)
    print("Connection successful!")
    return client


def create_collection(client: MilvusClient, collection_name: str, dim: int):
    """Create collection with schema"""
    print(f"Checking if collection exists: {collection_name}")
    if client.has_collection(collection_name):
        print(f"Collection already exists, dropping: {collection_name}")
        client.drop_collection(collection_name)

    schema = client.create_schema(enable_dynamic_field=True)

    schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field(
        "python", DataType.VARCHAR, max_length=65535, enable_analyzer=True, enable_match=True
    )
    schema.add_field("node", DataType.VARCHAR, max_length=65535)
    schema.add_field("java", DataType.VARCHAR, max_length=65535)
    schema.add_field("go", DataType.VARCHAR, max_length=65535)
    schema.add_field("csharp", DataType.VARCHAR, max_length=65535)
    schema.add_field("restful", DataType.VARCHAR, max_length=65535)
    schema.add_field("file_name", DataType.VARCHAR, max_length=512)
    schema.add_field("dense", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)

    bm25_function = Function(
        name="python_bm25_emb",
        input_field_names=["python"],
        output_field_names=["sparse"],
        function_type=FunctionType.BM25,
    )
    schema.add_function(bm25_function)

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        description="multi lang docs collection",
    )
    print(f"Collection created successfully: {collection_name}")


def create_index(
    client: MilvusClient,
    collection_name: str,
    index_type: str = "IVF_FLAT",
    metric_type: str = "IP",
):
    """Create indexes"""
    print("Creating indexes...")
    index_params = client.prepare_index_params()

    print("Creating dense vector index...")
    index_params.add_index(
        field_name="dense",
        index_name="dense_index",
        index_type=index_type,
        metric_type=metric_type,
    )

    print("Creating sparse vector index...")
    index_params.add_index(
        field_name="sparse",
        index_name="sparse_index",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
        params={"inverted_index_algo": "DAAT_MAXSCORE"},
    )

    print("Starting index creation...")
    client.create_index(collection_name, index_params)
    print("Indexes created successfully!")

    print("Index information:")
    index_names = client.list_indexes(collection_name)
    print(f"Indexes for collection {collection_name}:", index_names)

    for index_name in index_names:
        index_info = client.describe_index(collection_name, index_name=index_name)
        print(f"Details for index {index_name}:", index_info)


def insert_data(client: MilvusClient, collection_name: str, df: pd.DataFrame):
    """Insert data into collection in batches"""
    print("Preparing to insert data...")

    total = len(df)
    batch_size = 1000
    data_to_insert = []

    for i, row in enumerate(df.itertuples()):
        if i % 100 == 0:
            print(f"Progress: {i}/{total}")

        # Convert string embedding to list of floats
        embedding_str = row.embedding
        if isinstance(embedding_str, str):
            try:
                # Remove any whitespace and convert to list of floats
                embedding = [float(x.strip()) for x in embedding_str.strip("[]").split(",")]
            except Exception as e:
                print(f"Error converting embedding for row {i}: {e}")
                continue
        else:
            embedding = embedding_str

        data_item = {
            "python": row.python_content if pd.notna(row.python_content) else "",
            "node": row.node_content if pd.notna(row.node_content) else "",
            "java": row.java_content if pd.notna(row.java_content) else "",
            "go": row.go_content if pd.notna(row.go_content) else "",
            "csharp": row.csharp_content if pd.notna(row.csharp_content) else "",
            "restful": row.restful_content if pd.notna(row.restful_content) else "",
            "file_name": row.python_path.split("/")[-1] if pd.notna(row.python_path) else "",
            "dense": embedding,
        }
        data_to_insert.append(data_item)

        if len(data_to_insert) >= batch_size or i == total - 1:
            client.insert(collection_name=collection_name, data=data_to_insert)
            print(f"Successfully inserted {len(data_to_insert)} records")
            data_to_insert = []

    print(f"All data inserted! Total records: {total}")


def main():
    parser = argparse.ArgumentParser(
        description="Process multi-language documents and insert into Milvus"
    )
    parser.add_argument(
        "--base-dir", required=True, help="Base directory containing all language documentation"
    )
    parser.add_argument("--collection", required=True, help="Milvus collection name")
    parser.add_argument("--output-csv", required=True, help="Output CSV file path")
    parser.add_argument("--milvus-uri", default="http://localhost:19530", help="Milvus server URI")
    parser.add_argument("--milvus-token", default="root:Milvus", help="Milvus authentication token")

    args = parser.parse_args()

    # Set up base directories
    base_dirs = {
        "python": os.path.join(args.base_dir, "pymilvus/v2.5.x/MilvusClient"),
        "node": os.path.join(args.base_dir, "milvus-sdk-node/v2.5.x"),
        "java": os.path.join(args.base_dir, "milvus-sdk-java/v2.5.x/v2"),
        "go": os.path.join(args.base_dir, "milvus-sdk-go/v2.4.x"),
        "csharp": os.path.join(args.base_dir, "milvus-sdk-csharp/v2.2.x"),
        "restful": os.path.join(args.base_dir, "milvus-restful/v2.4.x/v2"),
    }

    # Process documents and generate embeddings
    processor = MultiLangDocsProcessor(base_dirs)
    processor.process_docs(args.output_csv)

    # Read the generated CSV file
    df = pd.read_csv(args.output_csv)
    sample_embedding = eval(df.iloc[0]["embedding"])
    dim = len(sample_embedding)
    print(f"Embedding dimension: {dim}")

    # Create Milvus client and collection
    client = create_milvus_client(args.milvus_uri, args.milvus_token)
    create_collection(client, args.collection, dim)
    create_index(client, args.collection)
    insert_data(client, args.collection, df)
    print("Insertion complete!")

    # Load collection and print stats
    client.load_collection(args.collection)
    stats = client.get_collection_stats(args.collection)
    print(stats)


if __name__ == "__main__":
    main()
