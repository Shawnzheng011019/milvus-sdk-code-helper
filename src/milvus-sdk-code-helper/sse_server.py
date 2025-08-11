import argparse
import logging
from typing import Any, Sequence

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool
from milvus_connector import MilvusConnector
from starlette.applications import Starlette
from starlette.routing import Route

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sse-milvus-sdk-code-helper-server")


class McpServer(MilvusConnector):
    def __init__(
        self,
        milvus_uri="http://localhost:19530",
        milvus_token="",
        db_name="default",
    ):
        super().__init__(milvus_uri=milvus_uri, milvus_token=milvus_token, db_name=db_name)
        self.app = Server("mcp-pymilvus-code-generator-server")
        self.setup_tools()

    def setup_tools(self):
        @self.app.list_tools()
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

        @self.app.call_tool()
        async def call_tool(
            name: str, arguments: Any
        ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
            name = name.replace("_", "-")
            if name == "milvus-pypmilvus-code-generator":
                query = arguments["query"]
                code = await self.pypmilvus_code_generator(query)
                return [TextContent(type="text", text=code)]
            elif name == "milvus-orm-client-code-convertor":
                query = arguments["query"]
                code = await self.orm_client_code_convertor(query)
                return [TextContent(type="text", text=code)]
            elif name == "milvus-code-translator":
                query = arguments["query"]
                source_language = arguments["source_language"]
                target_language = arguments["target_language"]
                code = await self.milvus_code_translator(
                    query, source_language, target_language
                )
                return [TextContent(type="text", text=code)]


def create_app(milvus_uri="http://localhost:19530", milvus_token="", db_name="default"):
    server = McpServer(milvus_uri=milvus_uri, milvus_token=milvus_token, db_name=db_name)
    sse = SseServerTransport("/message")

    class HandleSSE:
        def __init__(self, sse, server):
            self.sse = sse
            self.server = server

        async def __call__(self, scope, receive, send):
            async with self.sse.connect_sse(scope, receive, send) as streams:
                await self.server.app.run(
                    streams[0], streams[1], self.server.app.create_initialization_options()
                )

    class HandleMessages:
        def __init__(self, sse):
            self.sse = sse

        async def __call__(self, scope, receive, send):
            await self.sse.handle_post_message(scope, receive, send)

    routes = [
        Route("/milvus-code-helper/sse", endpoint=HandleSSE(sse, server), methods=["GET"]),
        Route("/message", endpoint=HandleMessages(sse), methods=["POST"]),
    ]

    return Starlette(routes=routes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PyMilvus Code Generation Helper (SSE Server)")
    parser.add_argument(
        "--milvus_uri", type=str, default="http://localhost:19530", help="Milvus server URI"
    )
    parser.add_argument("--milvus_token", type=str, default="", help="Milvus server token")
    parser.add_argument("--db_name", type=str, default="default", help="Milvus database name")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=23333, help="Port to run the server on")

    args = parser.parse_args()

    app = create_app(
        milvus_uri=args.milvus_uri, milvus_token=args.milvus_token, db_name=args.db_name
    )
    uvicorn.run(app, host=args.host, port=args.port)
