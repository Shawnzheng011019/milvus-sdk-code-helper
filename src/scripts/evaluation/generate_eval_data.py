import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from server import PymilvusServer

# Given a document, generate a list query, each of which is a query string to generate code. Return in List[str] format.
QUERY_GENERATION_PROMPT = """
Given a document, generate a list query, each of which is a query string to generate python code. Return in List[str] format. 

Document: 

<document>
{doc}
</document>

The generated queries:
"""


def literal_eval(response_content: str):
    import ast
    import re

    response_content = response_content.strip()

    # remove content between <think> and </think>, especial for DeepSeek reasoning model
    if "<think>" in response_content and "</think>" in response_content:
        end_of_think = response_content.find("</think>") + len("</think>")
        response_content = response_content[end_of_think:]

    try:
        if response_content.startswith("```") and response_content.endswith("```"):
            if response_content.startswith("```python"):
                response_content = response_content[9:-3]
            elif response_content.startswith("```json"):
                response_content = response_content[7:-3]
            elif response_content.startswith("```str"):
                response_content = response_content[6:-3]
            elif response_content.startswith("```\n"):
                response_content = response_content[4:-3]
            else:
                raise ValueError("Invalid code block format")
        result = ast.literal_eval(response_content.strip())
    except Exception:
        matches = re.findall(r"(\[.*?\]|\{.*?\})", response_content, re.DOTALL)

        if len(matches) != 1:
            raise ValueError(f"Invalid JSON/List format for response content:\n{response_content}")

        json_part = matches[0]
        return ast.literal_eval(json_part)

    return result


def test_data_generation(milvus_uri="http://localhost:19530", save_path="data.json"):
    import json

    MAX_NUM = 16384
    server = PymilvusServer(milvus_uri=milvus_uri)
    res = server.milvus_client.query(
        collection_name="pymilvus_user_guide",
        output_fields=["content", "metadata"],
        limit=MAX_NUM,
    )

    all_docs = [row["content"] for row in res]
    all_file_name = [row["metadata"] for row in res]

    data = []

    for i, doc in enumerate(all_docs):
        print(f"Process {i + 1}/{len(all_docs)} doc: {all_file_name[i]}")
        gold_doc = doc

        response = server.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": QUERY_GENERATION_PROMPT.format(doc=doc)},
            ],
        )
        query_list = literal_eval(response.choices[0].message.content)
        data.append(
            {
                "gold_doc": gold_doc,
                "file_name": all_file_name[i],
                "query_list": query_list,
            }
        )

    with open(save_path, "w") as f:
        json.dump(data, f, indent=4)


if __name__ == "__main__":
    test_data_generation(milvus_uri="http://localhost:19530", save_path="data.json")
