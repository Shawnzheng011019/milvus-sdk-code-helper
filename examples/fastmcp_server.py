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
        If the request contains keywords like 'translate' or 'convert' or 'to client' or 'to orm', do not use this tool.
        
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

#### 5. Keyword Lists

* **milvus\_code\_translator**:

  * Keywords: `translate`, `from Python`, `to C#`, `language conversion`, `rewrite in Java`

* **orm\_client\_code\_convertor**:

  * Keywords: `ORM`, `client`, `Django ORM style`

* **Generate trigger**:

  * Keywords: `generate`, `create new`, `build`, `design from scratch` (only valid when no translation/language pair)
        """
        return prompt

    # Expose connector for advanced usage/debugging
    app.milvus_connector = milvus_connector  # type: ignore[attr-defined]
    return app


if __name__ == "__main__":  # pragma: no cover
    main() 