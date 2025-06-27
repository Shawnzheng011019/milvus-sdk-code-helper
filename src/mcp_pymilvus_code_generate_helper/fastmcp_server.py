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
            query: A string of Milvus API names in list format to translate from one programming language to another (e.g., ['create_collection', 'insert', 'search'])
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
        Tool selection priority for Milvus code tasks:

        1. Milvus Code Generation:
           - Trigger: Request contains keywords like 'generate', 'sample code', 'how to write' and mentions 'pymilvus' or 'milvus'.
           - Use for generating or writing pymilvus/milvus code.
           - Do not use for language translation or ORM conversion.

        2. Milvus Client ↔ ORM Code Conversion:
           - Trigger: Request contains 'orm' and any of 'convert', 'translate', 'to client', or 'to orm'.
           - Use for converting or translating between ORM and client code.
           - Do not use for general code generation or language translation.

        3. Milvus Code Translation Between Languages:
           - Trigger: Request contains 'translate to' and a non-Python programming language (e.g., 'java', 'nodejs', 'go'), with both source and target languages specified.
           - Use for translating Milvus code between different programming languages.
           - Only use if the target language is not Python.

        Always follow this priority order and trigger conditions when selecting tools for Milvus-related code tasks.
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
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for http/sse transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for http/sse transport")
    parser.add_argument("--path", type=str, default="/mcp", help="Path for http transport")
    parser.add_argument("--transport", type=str, default="http", choices=["stdio", "http", "sse"], help="Transport protocol (default: http)")
    parser.add_argument("--stateless", action="store_true", default=True, help="Enable stateless HTTP/SSE mode (default: True)")

    args = parser.parse_args()

    # Perform blocking first-time document preparation (steps 1-4)
    try:
        update_documents(args.milvus_uri, args.milvus_token)
    except Exception as exc:
        logger.error("Initial document update failed: %s", exc, exc_info=True)

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
