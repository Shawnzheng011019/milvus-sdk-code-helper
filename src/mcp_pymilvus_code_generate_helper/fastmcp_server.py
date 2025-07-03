#!/usr/bin/env python3
"""
FastMCP-based PyMilvus Code Generation Helper Server

This is a rewrite of the original stdio_server.py using the FastMCP framework.
It provides the same three tools for Milvus code generation and translation.
"""

import argparse
import logging

# Import new synchronous updater & scheduler
from doc_updater import update_documents
from fastmcp import FastMCP
from milvus_connector import MilvusConnector
from scheduler import start_weekly_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastmcp-pymilvus-code-generate-server")


def create_app(
    milvus_uri: str = "http://localhost:19530",
    milvus_token: str = "",
    db_name: str = "default",
    repo_url: str = "https://github.com/milvus-io/web-content.git",  # kept for future use
    local_repo_path: str = "./web-content",
    repo_branch: str = "master",
) -> FastMCP:
    """Create and configure the FastMCP application"""
    
    # Create FastMCP app
    app = FastMCP("PyMilvus Code Generation Helper 🚀")
    
    # Initialize Milvus connector
    milvus_connector = MilvusConnector(
        milvus_uri=milvus_uri,
        milvus_token=milvus_token,
        db_name=db_name,
    )
    
    @app.tool
    async def milvus_code_generator(query: str) -> str:
        """
        Generate or provide sample pymilvus/milvus code based on user input in natural language.
        
        Trigger: Use this tool if the request contains keywords like 'generate', 'sample code', 'how to write' and mentions 'pymilvus' or 'milvus'.
        Do NOT use for ORM conversion or language translation tasks.
        
        Args:
            query: User query for generating code
        Returns:
            Related pymilvus code/documents to help generate code from user query
        """
        logger.info(f"Generating PyMilvus code for query: {query[:100]}...")
        result = await milvus_connector.pypmilvus_code_generator(query)
        return result
    
    @app.tool
    async def orm_client_code_convertor(query: str) -> str:
        """
        Convert or translate between ORM and PyMilvus client code formats.
        
        Trigger: Use this tool if the request contains 'orm' and any of 'convert', 'to client', or 'to orm'.
        Do NOT use for general code generation or language translation tasks.
        
        Args:
            query: A string of Milvus API names in list format from user query and code context to translate between orm and milvus client
        Returns:
            Related orm and pymilvus client code/documents for conversion
        """
        logger.info(f"Converting ORM/Client code for query: {query[:100]}...")
        result = await milvus_connector.orm_client_code_convertor(query)
        return result
    
    @app.tool
    async def milvus_code_translator(query: str, source_language: str, target_language: str) -> str:
        """
        Translate Milvus code between different programming languages.
        
        Trigger: Use this tool if the request contains 'translate to' and a non-Python programming language (e.g., 'java', 'nodejs', 'go'), with both source and target languages specified. Only use if the target language is not Python.
        Do NOT use for general code generation or ORM conversion tasks.
        
        Args:
            query: A string of Milvus API names in list format to translate from one programming language to another. CRITICAL: Must use escaped double quotes format like [\"create_collection\", \"create_index\", \"insert\", \"search\", \"hybrid_search\"]. Do NOT use single quotes or unescaped format.
            source_language: Source programming language (e.g., 'python', 'java', 'go', 'csharp', 'node', 'restful')
            target_language: Target programming language (e.g., 'python', 'java', 'go', 'csharp', 'node', 'restful')
        Returns:
            Related documents and code snippets for translation between programming languages
        """
        logger.info(f"Translating code from {source_language} to {target_language} for query: {query[:100]}...")
        result = await milvus_connector.milvus_code_translator(query, source_language, target_language)
        return result
    
    @app.prompt
    def tool_selection_guidance(user_input: str) -> str:
        prompt = """
### Tool Selection Prompt

#### 1. Tool Functions & Keyword Conditions

**milvus\_code\_translator** (for language conversion):

* **Trigger** when the request includes:

  * Translation keywords: `translate`, `port`, `migrate`
  * A clear source-to-target language pair, formatted as `from [source_lang] to [target_lang]` or explicit language names in context

**orm\_client\_code\_convertor** (for style conversion):

* **Trigger** when the request includes:

  * ORM/client-related keywords: `ORM`, `client`, `SQLAlchemy`, `Django ORM`
  * Style-related keywords: `style`, `format`, `convention`, `PEP8`, `naming`, `indentation`, `adapt style`

**milvus\_code\_generator** (for code creation):

* **Trigger** when the request includes:

  * Code generation keywords: `generate`, `create`, `build`, `design`, `construct`, `new module`, `from scratch`
  * No language/style conversion keywords

#### 2. Step-by-Step Decision Logic

1. **Check for language translation first**:

   * If the request contains **both**:

     * A translation keyword: `translate`, `port`, `migrate`
     * A source-to-target language pair (e.g., `from Python to Java`)
   * **Use** `milvus_code_translator`
   * **Exit** the decision process

2. **Check for style conversion next**:

   * If the request contains:

     * ORM/client-related keywords: `ORM`, `client`, `SQLAlchemy`, `Django ORM`
     * Style-related keywords: `style`, `format`, `PEP8`, `naming`, `indentation`, `adapt style`
   * **Use** `orm_client_code_convertor`
   * **Exit** the decision process

3. **Default to code generation**:

   * If the request contains:

     * Code generation keywords: `generate`, `create`, `build`, `design`, `construct`, `new module`, `from scratch`
   * **Use** `milvus_code_generator`

#### 3. Critical Rules & Exceptions

* **Language translation requires both languages**:

  * Invalid: "Translate Milvus code" (missing source/target)
  * Valid: "Translate Milvus from Python to JavaScript"

* **Style conversion requires ORM/client context**:

  * Invalid: "Convert code to PEP8" (no ORM/client)
  * Valid: "Convert Milvus ORM client to PEP8"

* **Priority rule**:

  * For requests combining translation and style (e.g., "Translate Java to Python and adapt to Flask style"), **use** `milvus_code_translator` first

#### 4. Anti-Error Mechanisms

* **Mandatory Language Pair for Translation**:

  * Invalid (will block translation): "Translate Milvus code to Python" (missing source language)
  * Valid: "Translate Milvus Java code to Python" (source=Java, target=Python)

* **Keyword Priority Hierarchy**:

  * `translate + language pair` > `ORM/client + style` > `generate/create`

#### 5. CRITICAL Query Format Requirements for milvus_code_translator

**MANDATORY FORMAT**: When calling milvus_code_translator, the query parameter MUST use escaped double quotes format:

* **CORRECT**: [\"create_collection\", \"create_index\", \"insert\", \"search\", \"hybrid_search\"]
* **WRONG**: ["create_collection", "create_index", "insert", "search", "hybrid_search"]
* **WRONG**: ['create_collection', 'create_index', 'insert', 'search', 'hybrid_search']

**Format Examples**:
* Single API: [\"create_collection\"]
* Multiple APIs: [\"create_collection\", \"insert\", \"search\"]
* Complex operations: [\"create_collection\", \"create_index\", \"insert\", \"search\", \"hybrid_search\", \"drop_collection\"]

**Why This Matters**: The system uses ast.literal_eval() to parse the query string. Unescaped quotes will cause parsing failures and incorrect results.

#### 6. Keyword Lists

* **milvus\_code\_translator**:

  * Keywords: `translate`, `from Python`, `to C#`, `language conversion`, `rewrite in Java`

* **orm\_client\_code\_convertor**:

  * Keywords: `ORM`, `client`, `Django ORM style`

* **Generate trigger**:

  * Keywords: `generate`, `create new`, `build`, `design from scratch` (only valid when no translation/language pair)
        """
        return prompt
    
    app.milvus_connector = milvus_connector  # attach for later use
    return app

def main():
    """Main entry point for the FastMCP server"""
    parser = argparse.ArgumentParser(description="PyMilvus Code Generation Helper (FastMCP)")
    parser.add_argument(
        "--milvus_uri",
        type=str,
        default="http://localhost:19530",
        help="Milvus server URI",
    )
    parser.add_argument("--milvus_token", type=str, default="", help="Milvus server token")
    parser.add_argument("--db_name", type=str, default="default", help="Milvus database name")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for http/sse transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for http/sse transport")
    parser.add_argument("--path", type=str, default="/mcp", help="Path for http transport")
    parser.add_argument("--transport", type=str, default="http", choices=["stdio", "http", "sse"], help="Transport protocol (default: http)")
    parser.add_argument("--stateless", action="store_true", default=True, help="Enable stateless HTTP/SSE mode (default: True)")

    args = parser.parse_args()

    # Start weekly background scheduler (decoupled from FastMCP)
    start_weekly_scheduler(args.milvus_uri, args.milvus_token)

    # Create FastMCP application (step 5)
    app = create_app(
        milvus_uri=args.milvus_uri,
        milvus_token=args.milvus_token,
        db_name=args.db_name,
    )

    if args.transport == "stdio":
        logger.info("Starting FastMCP server with STDIO transport...")
        app.run(transport="stdio")
    elif args.transport == "http":
        logger.info(f"Starting FastMCP server with HTTP transport on {args.host}:{args.port}{args.path} (stateless=True)...")
        app.run(transport="http", host=args.host, port=args.port, path=args.path)
    elif args.transport == "sse":
        logger.info(f"Starting FastMCP server with SSE transport on {args.host}:{args.port}...")
        app.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
