import argparse
import os

from insert_embedding_2_vector_db import (
    create_collection,
    create_index,
    create_milvus_client,
    insert_data,
    read_embeddings_csv,
)
from md_2_embedding import generate_embeddings


def process_docs_to_milvus(
    docs_dir_path, milvus_uri, milvus_token, collection_name, output_csv="embeddings.csv"
):
    """
    Process markdown documents to embeddings and insert them into Milvus.

    Args:
        docs_dir_path: Path to the directory containing markdown files
        milvus_uri: URI of the Milvus server
        collection_name: Name of the collection to create/use in Milvus
        output_csv: Name of the CSV file to store embeddings (default: embeddings.csv)
    """
    print("Step 1: Converting documents to embeddings...")
    # Generate embeddings and save to CSV
    generate_embeddings(docs_dir_path, output_csv)

    print("\nStep 2: Inserting embeddings into Milvus...")
    # Create Milvus client
    client = create_milvus_client(milvus_uri, milvus_token)

    # Read the embeddings CSV
    df, max_content_length = read_embeddings_csv(output_csv)

    # Get embedding dimension from first row
    sample_embedding = eval(df.iloc[0]["embedding"])
    dim = len(sample_embedding)
    print(f"Embedding dimension: {dim}")

    # Create collection and indexes
    create_collection(client, collection_name, max_content_length, dim)
    create_index(client, collection_name)

    # Insert data
    insert_data(client, collection_name, df)

    # Load collection and get stats
    client.load_collection(collection_name)
    stats = client.get_collection_stats(collection_name)
    print("\nCollection statistics:")
    print(stats)

    print("\nProcess completed successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Process markdown documents: generate embeddings and insert into Milvus database"
    )

    parser.add_argument(
        "--docs-dir", required=True, help="Path to the directory containing markdown documents"
    )
    parser.add_argument("--collection", required=True, help="Milvus collection name")
    parser.add_argument("--output-csv", required=True, help="Output CSV file path")
    parser.add_argument("--milvus-uri", default="http://localhost:19530", help="Milvus server URI")
    parser.add_argument("--milvus-token", default="root:Milvus", help="Milvus authentication token")

    args = parser.parse_args()

    # Check if the document directory exists
    if not os.path.exists(args.docs_dir):
        print(f"Error: Document directory does not exist: {args.docs_dir}")
        return

    # Check and set Milvus URI from args or environment variables
    if not args.milvus_uri:
        args.milvus_uri = os.getenv("MILVUS_ENDPOINT") or os.getenv("ZILLIZ_CLOUD_URI")
        if not args.milvus_uri:
            print(
                "Error: No Milvus URI provided. Please specify --milvus-uri or set MILVUS_ENDPOINT/ZILLIZ_CLOUD_URI environment variable"
            )
            return
    # Check and set Milvus token from args or environment variables
    if not args.milvus_token:
        args.milvus_token = os.getenv("MILVUS_TOKEN") or os.getenv("ZILLIZ_CLOUD_API_KEY")
        if not args.milvus_token:
            print(
                "Error: No Milvus token provided. Please specify --milvus-token or set MILVUS_TOKEN/ZILLIZ_CLOUD_API_KEY environment variable"
            )
            return
    # Execute the processing workflow
    process_docs_to_milvus(
        docs_dir_path=args.docs_dir,
        milvus_uri=args.milvus_uri,
        milvus_token=args.milvus_token,
        collection_name=args.collection,
        output_csv=args.output_csv,
    )


if __name__ == "__main__":
    main()
