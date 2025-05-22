import ast

import pandas as pd
from pymilvus import DataType, Function, FunctionType, MilvusClient


def create_milvus_client(uri="http://localhost:19530", token="root:Milvus"):
    """Create a Milvus client with the given URI"""
    print(f"Connecting to Milvus server: {uri}")
    client = MilvusClient(uri=uri, token=token)
    print("Connection successful!")

    return client


def read_embeddings_csv(file_path):
    """Read embeddings from CSV file and calculate max content length"""
    print(f"Reading embeddings file: {file_path}")
    df = pd.read_csv(file_path)
    print(f"Read complete, {len(df)} records loaded")

    # Calculate maximum content length for VARCHAR field size
    max_content_length = df["content"].str.len().max()
    print(f"Maximum content length: {max_content_length} characters")

    return df, max_content_length


def create_collection(client, collection_name, max_content_length, dim):
    """Create a collection with schema for hybrid search"""
    print(f"Checking if collection exists: {collection_name}")
    if client.has_collection(collection_name):
        print(f"Collection already exists, dropping existing collection: {collection_name}")
        client.drop_collection(collection_name)

    schema = client.create_schema(enable_dynamic_field=True)

    schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field(
        "content", DataType.VARCHAR, max_length=65535, enable_analyzer=True, enable_match=True
    )
    schema.add_field("metadata", DataType.VARCHAR, max_length=512)
    schema.add_field("dense", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)

    bm25_function = Function(
        name="content_bm25_emb",
        input_field_names=["content"],
        output_field_names=["sparse"],
        function_type=FunctionType.BM25,
    )

    schema.add_function(bm25_function)

    # Create collection
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        description="User Guide Collection",
    )

    print(f"Collection created successfully: {collection_name}")


def create_index(client, collection_name, index_type="IVF_FLAT", metric_type="IP"):
# def create_index(client, collection_name, index_type="IVF_FLAT", metric_type="COSINE"):
    """Create indexes for dense and sparse vectors"""
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


def insert_data(client, collection_name, df):
    """Insert data into collection in batches"""
    print("Preparing to insert data...")

    total = len(df)
    batch_size = 1000

    data_to_insert = []

    for i, row in enumerate(df.itertuples()):
        if i % 100 == 0:
            print(f"Progress: {i}/{total}")

        embedding = ast.literal_eval(row.embedding)
        data_item = {"content": row.content, "metadata": row.file_name, "dense": embedding}
        data_to_insert.append(data_item)

        if len(data_to_insert) >= batch_size or i == total - 1:
            client.insert(collection_name=collection_name, data=data_to_insert)
            print(f"Successfully inserted {len(data_to_insert)} records")
            data_to_insert = []

    print(f"All data inserted! Total records: {total}")


if __name__ == "__main__":
    uri = "http://10.100.30.11:19530"
    collection_name = "pymilvus_user_guide"
    # collection_name = "mcp_orm"
    # collection_name = "mcp_milvus_client"
    # input_file = "user_guide.csv"
    # input_file = "../../../doc_embedding/user_guide.csv"
    input_file = "doc_embedding/user_guide_unsplit.csv"
    # input_file = "ORM.csv"
    # input_file = "MilvusClient.csv"

    client = create_milvus_client(uri)

    df, max_content_length = read_embeddings_csv(input_file)

    sample_embedding = ast.literal_eval(df.iloc[0]["embedding"])
    dim = len(sample_embedding)
    print(f"Embedding dimension: {dim}")

    create_collection(client, collection_name, max_content_length, dim)
    create_index(client, collection_name)
    insert_data(client, collection_name, df)
    print("Insertion complete!")

    client.load_collection(collection_name)

    stats = client.get_collection_stats(collection_name)
    print(stats)
