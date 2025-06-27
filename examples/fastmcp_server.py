#!/usr/bin/env python3
"""
Lightweight FastMCP PyMilvus Code Generation Helper Server

This variant starts the FastMCP server without executing the initial document
synchronization or launching the weekly background scheduler. It is intended
for scenarios where the Milvus collections have already been prepared and a
quick startup is preferred.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Final

# Ensure the project src directory is importable when running from repository root.
PROJECT_ROOT: Final[str] = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
SRC_PATH: Final[str] = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# pylint: disable=wrong-import-position
from fastmcp import FastMCP  # noqa: E402
from mcp_pymilvus_code_generate_helper.milvus_connector import MilvusConnector  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastmcp-pymilvus-code-generate-server-light")


def main() -> None:
    """Entry point for the lightweight FastMCP server"""
    parser = argparse.ArgumentParser(
        description="PyMilvus Code Generation Helper (FastMCP, no document update)",
    )
    parser.add_argument(
        "--milvus_uri",
        type=str,
        default="http://localhost:19530",
        help="Milvus server URI",
    )
    parser.add_argument(
        "--milvus_token", type=str, default="", help="Milvus server token"
    )
    parser.add_argument(
        "--db_name", type=str, default="default", help="Milvus database name"
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host for http/sse transport"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for http/sse transport"
    )
    parser.add_argument(
        "--path", type=str, default="/mcp", help="Path for http transport"
    )
    parser.add_argument(
        "--transport",
        type=str,
        default="http",
        choices=["stdio", "http", "sse"],
        help="Transport protocol (default: http)",
    )
    parser.add_argument(
        "--stateless",
        action="store_true",
        default=True,
        help="Enable stateless HTTP/SSE mode (default: True)",
    )

    args = parser.parse_args()

    # Create FastMCP application without document update or scheduler.
    app = create_app(
        milvus_uri=args.milvus_uri,
        milvus_token=args.milvus_token,
        db_name=args.db_name,
    )

    logger.info("Starting lightweight FastMCP server (no document sync)…")

    if args.transport == "stdio":
        app.run(transport="stdio")
    elif args.transport == "http":
        app.run(
            transport="http",
            host=args.host,
            port=args.port,
            path=args.path,
        )
    elif args.transport == "sse":
        app.run(
            transport="sse",
            host=args.host,
            port=args.port,
        )


# --------------------------------------------------------------------------------------
# Local lightweight `create_app` implementation (decoupled from the full server module)
# --------------------------------------------------------------------------------------


def create_app(
    milvus_uri: str = "http://localhost:19530",
    milvus_token: str = "",
    db_name: str = "default",
    repo_url: str = "https://github.com/milvus-io/web-content.git",  # kept for future use
    local_repo_path: str = "./web-content",
    repo_branch: str = "master",
) -> FastMCP:
    """Create and configure a minimal FastMCP application (no scheduler or doc sync)."""

    # Create FastMCP app
    app = FastMCP("PyMilvus Code Generation Helper 🚀")

    # Initialize Milvus connector
    milvus_connector = MilvusConnector(
        milvus_uri=milvus_uri,
        milvus_token=milvus_token,
        db_name=db_name,
    )

    # ------------------------------------------------------------------
    # Tool 1: Generate/Provide sample PyMilvus code snippets
    # ------------------------------------------------------------------
    @app.tool
    async def milvus_code_generator(query: str) -> str:  # noqa: D401
        """
        Generate or provide sample pymilvus/milvus code based on user input in natural language.
        
        Trigger: Use this tool if the request contains keywords like 'generate', 'sample code', 'how to write' and mentions 'pymilvus' or 'milvus'.
        Do NOT use for ORM conversion or language translation tasks.
        
        Args:
            query: User query for generating code
        Returns:
            Related pymilvus code/documents to help generate code from user query
        """
        logger.info("Generating PyMilvus code for query: %s", query[:100])
        return await milvus_connector.pypmilvus_code_generator(query)

    # ------------------------------------------------------------------
    # Tool 2: ORM ↔ Client conversion helper
    # ------------------------------------------------------------------
    @app.tool
    async def orm_client_code_convertor(query: str) -> str:  # noqa: D401
        """
        Convert or translate between ORM and PyMilvus client code formats.
        
        Trigger: Use this tool if the request contains 'orm' and any of 'convert', 'to client', or 'to orm'.
        Do NOT use for general code generation or language translation tasks.
        
        Args:
            query: A string of Milvus API names in list format from user query and code context to translate between orm and milvus client
        Returns:
            Related orm and pymilvus client code/documents for conversion
        """
        logger.info("Converting ORM/Client code for query: %s", query[:100])
        return await milvus_connector.orm_client_code_convertor(query)

    # ------------------------------------------------------------------
    # Tool 3: Cross-language Milvus code translator
    # ------------------------------------------------------------------
    @app.tool
    async def milvus_code_translator(query: str, source_language: str, target_language: str) -> str:  # noqa: D401
        """
        Translate Milvus code between different programming languages.
        
        Trigger: Use this tool if the request contains 'translate to' and a non-Python programming language (e.g., 'java', 'nodejs', 'go'), with both source and target languages specified. Only use if the target language is not Python.
        Do NOT use for general code generation or ORM conversion tasks.
        
        Args:
            query: A string of Milvus API names in list format to translate from one programming language to another (e.g., ['create_collection', 'insert', 'search'])
            source_language: Source programming language (e.g., 'python', 'java', 'go', 'csharp', 'node', 'restful')
            target_language: Target programming language (e.g., 'python', 'java', 'go', 'csharp', 'node', 'restful')
        Returns:
            Related documents and code snippets for translation between programming languages
        """
        logger.info(
            "Translating code from %s to %s for query: %s",
            source_language,
            target_language,
            query[:100],
        )
        return await milvus_connector.milvus_code_translator(query, source_language, target_language)

    # ------------------------------------------------------------------
    # Prompt guiding the LLM on when to invoke which tool
    # ------------------------------------------------------------------
    @app.prompt
    def tool_selection_guidance(user_input: str) -> str:  # noqa: D401
        prompt = """
        # !!!Always use tools for milvus code generation, conversion, and translation tasks **in the order of priority below**.  

#### 1. **Milvus Code Generation (Highest Priority)**  
- **Trigger**:  
  - Request contains **`generate`** **OR** **`sample code`** **OR** **`how to write`** **AND** **`pymilvus`/`milvus`**.  
  - **Exclude** requests with explicit language translation keywords (e.g., `to java`, `nodejs`).  
- **Action**:  
  - Call `milvus_pypmilvus_code_generate_helper` with `query` = user's request.  

#### 2. **Milvus Client ↔ ORM Code Conversion (Medium Priority)**  
- **Trigger**:  
  - Request contains **`orm`** **AND** (`convert`/`translate`/`to client`/`to orm`).  
  - **Exclude** requests with explicit programming language names (e.g., `java`, `python`).  
- **Action**:  
  - Call `milvus_orm_client_code_convert_helper` with `query`.  

#### 3. **Milvus Code Translation Between Languages (Lowest Priority)**  
- **Trigger**:  
  - Request contains **`translate`** **AND** a **programming language different from the first programming language in the request**.  
  - **Must include** both `source_language` and `target_language`.  
- **Action**:  
  - Call `milvus_code_translate_helper` with `query`, `source_language`, and `target_language`.  

#### **Critical Exclusion Rules**  
1. **Do not call Tool 1 (`code generation`) if** the request mentioned keyword `translate` or `convert` or `to client` or `to orm`.  
2. **Do not call Tool 3 (`translation`) if** the request does not mention a **non-Python language** (e.g., only `pymilvus`/`python` is present).  
3. **Priority Enforcement**:  
  - If a request matches **both Tool 1 and Tool 3** (e.g., "Generate code to java"), **force-trigger Tool 1** (code generation takes precedence over translation).  
4. **Parameter Validation for Tool 3**:  
  - If `target_language` is missing, **do not call Tool 3**; instead, use fallback to ask:  
    *"Please specify the target programming language (e.g., 'to java' or 'to nodejs')"*.  

#### **Fallback Rule**  
- **When to Use**:  
  - Request does not match any tool's trigger (e.g., "How does Milvus indexing work?").  
  - Tool 3 is triggered but missing `target_language`.  
- **Response**:  
  *"Please clarify your request:  
  1. Code Generation (e.g., 'Generate pymilvus code for search')  
  2. ORM/Client Conversion (e.g., 'Convert orm to pymilvus')  
  3. Language Translation (e.g., 'Translate to java')"*  

If you meet the milvus code translation between different programming language task or convert between orm and milvus client, you must identify all API calls of the selected codes related to the Milvus SDK. The "query" argument should be a list of API call descriptions.

Here is the examples:
Example 1
Context:
```
from pymilvus import MilvusClient, DataType

CLUSTER_ENDPOINT = "http://localhost:19530"
TOKEN = "root:Milvus"

# 1. Set up a Milvus client
client = MilvusClient(
    uri=CLUSTER_ENDPOINT,
    token=TOKEN 
)

# 2. Create a collection in quick setup mode
client.create_collection(
    collection_name="quick_setup",
    dimension=5
)

res = client.get_load_state(
    collection_name="quick_setup"
)

print(res)
```
Parsed arguments of tool using:
["create_collection", "get_load_state"]

Example 2
Context:
```
from pymilvus import MilvusClient

client = MilvusClient(uri="http://localhost:19530", token="root:Milvus")

if not client.has_collection("my_collection"):
    client.create_collection(collection_name="my_collection", dimension=128)

client.insert(
    collection_name="my_collection",
    data=[{"vector": [0.1, 0.2, 0.3, 0.4, 0.5]}]
)

client.flush(["my_collection"])
```
Parsed arguments of tool using:
["has_collection", "create_collection", "insert", "flush"]
        """
        return prompt

    # Expose connector for advanced usage/debugging
    app.milvus_connector = milvus_connector  # type: ignore[attr-defined]
    return app


if __name__ == "__main__":  # pragma: no cover
    main() 