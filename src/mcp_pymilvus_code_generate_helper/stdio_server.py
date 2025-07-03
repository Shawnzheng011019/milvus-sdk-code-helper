import argparse
import asyncio
import logging
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool
from milvus_connector import MilvusConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stdio-mcp-pymilvus-code-generate-server")


def main():
    parser = argparse.ArgumentParser(description="PyMilvus Code Generation Helper")
    parser.add_argument(
        "--milvus_uri",
        type=str,
        default="http://localhost:19530",
        help="Milvus server URI",
    )
    parser.add_argument("--milvus_token", type=str, default="", help="Milvus server token")
    parser.add_argument("--db_name", type=str, default="default", help="Milvus database name")

    args = parser.parse_args()

    pymilvus_server = MilvusConnector(
        milvus_uri=args.milvus_uri, milvus_token=args.milvus_token, db_name=args.db_name
    )

    server = Server("stdio-mcp-pymilvus-code-generate-helper-server")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="milvus-pypmilvus-code-generator",
                description="Find related pymilvus code/documents to help generating code from user input in natural language",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "User query for generating code",
                        }
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="milvus-orm-client-code-convertor",
                description="Find related orm and pymilvus client code/documents to help converting orm code to pymilvus client (or vice versa)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A string of Milvus API names in list format from user query and code context to translate between orm and milvus client",
                        }
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="milvus-code-translator",
                description="Find related documents and code snippets in different programming languages for milvus code translation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A string of Milvus API names in list format to translate from one programming language to another. CRITICAL: Must use escaped double quotes format like [\"create_collection\", \"create_index\", \"insert\", \"search\", \"hybrid_search\"]. Do NOT use single quotes or unescaped format.",
                        },
                        "source_language": {
                            "type": "string",
                            "description": "Source programming language (e.g., 'python', 'java', 'go', 'csharp', 'node', 'restful')",
                        },
                        "target_language": {
                            "type": "string",
                            "description": "Target programming language (e.g., 'python', 'java', 'go', 'csharp', 'node', 'restful')",
                        },
                    },
                    "required": ["query", "source_language", "target_language"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: Any
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        name = name.replace("_", "-")
        if name == "milvus-pypmilvus-code-generator":
            query = arguments["query"]
            code = await pymilvus_server.pypmilvus_code_generator(query)
            return [TextContent(type="text", text=code)]
        elif name == "milvus-orm-client-code-convert-helper":
            query = arguments["query"]
            code = await pymilvus_server.orm_client_code_convertor(query)
            return [TextContent(type="text", text=code)]
        elif name == "milvus-code-translator":
            query = arguments["query"]
            source_language = arguments["source_language"]
            target_language = arguments["target_language"]
            code = await pymilvus_server.milvus_code_translator(
                query, source_language, target_language
            )
            return [TextContent(type="text", text=code)]

    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server running with stdio transport")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
