import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.mcp_pymilvus_code_generate_helper.server import PymilvusServer

def test_search_similar_documents(milvus_uri="http://localhost:19530", top_k=5):
    """
    Test the search_similar_documents method of PymilvusServer
    Use queries and gold standard documents from data.json
    """
    print("Starting document search test...")
    
    server = PymilvusServer(milvus_uri=milvus_uri)
    
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            test_data = json.load(f)
        print(f"Successfully loaded test data, total {len(test_data)} test cases")
    except Exception as e:
        print(f"Failed to load test data: {e}")
        return
    
    success_count = 0
    total_queries = 0
    
    for i, item in enumerate(test_data):
        gold_doc = item.get("gold_doc", "")
        true_file_name = item.get("file_name", "")
        query_list = item.get("query_list", [])
        
        if not query_list or not gold_doc:
            print(f"Skipping test case {i+1}, data incomplete")
            continue
        
        print(f"\n\nTest case {i+1}/{len(test_data)}")

        for j, query in enumerate(query_list):
            total_queries += 1
            print(f"\nTest query {j+1}/{len(query_list)}: '{query}'")
            
            try:
                results = server.search_similar_documents(
                    query_text=query,
                    top_k=top_k,
                )

                found = False
                for result in results:
                    for k, record in enumerate(result):
                        distance = record.get('distance', 0)
                        record = record.get('entity', {})
                        content = record.get('content', '')
                        file_name = record.get('metadata', '')

                        print(f"Result {k+1}: {file_name} (similarity: {distance:.4f}) correct doc: {true_file_name}")

                        if file_name == true_file_name:
                            found = True
                            success_count += 1
                            print(f"✓ Successfully found correct document! Rank: {k+1}")
                            break

                    if not found:
                        print(f"✗ Failed to find correct document")
            
            except Exception as e:
                print(f"Error during search: {e}")
    
    print("\n\nTest completed!")
    if total_queries > 0:
        success_rate = (success_count / total_queries) * 100
        print(f"Success rate in top {top_k} results: {success_count}/{total_queries} ({success_rate:.2f}%)")
    else:
        print("No queries were executed")


if __name__ == "__main__":
    test_search_similar_documents()
