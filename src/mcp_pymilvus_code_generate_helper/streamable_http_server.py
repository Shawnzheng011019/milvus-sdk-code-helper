import argparse
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any, Sequence

import uvicorn
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool
from milvus_connector import MilvusConnector
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streamable-http-mcp-pymilvus-code-generate-helper-server")


class McpServer(MilvusConnector):
    def __init__(
        self,
        milvus_uri="http://localhost:19530",
        milvus_token="",
        db_name="default",
        stateless_http: bool = False,
        enable_auto_update=False,
        update_interval_minutes=60,
        repo_url="https://github.com/milvus-io/web-content.git",
        local_repo_path="./web-content",
        repo_branch="master"
    ):
        super().__init__(
            milvus_uri=milvus_uri,
            milvus_token=milvus_token,
            db_name=db_name,
            enable_auto_update=enable_auto_update,
            update_interval_minutes=update_interval_minutes,
            repo_url=repo_url,
            local_repo_path=local_repo_path
        )
        self.stateless_http = stateless_http

        # Create MCP server
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
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]


def create_app(
    milvus_uri="http://localhost:19530",
    milvus_token="",
    db_name="default",
    stateless_http: bool = False,
    enable_auto_update=False,
    update_interval_minutes=60,
    repo_url="https://github.com/milvus-io/web-content.git",
    local_repo_path="./web-content",
    repo_branch="master"
) -> Starlette:
    """Create a Starlette app with StreamableHTTP transport for MCP."""
    server = McpServer(
        milvus_uri=milvus_uri,
        milvus_token=milvus_token,
        db_name=db_name,
        stateless_http=stateless_http,
        enable_auto_update=enable_auto_update,
        update_interval_minutes=update_interval_minutes,
        repo_url=repo_url,
        local_repo_path=local_repo_path,
        repo_branch=repo_branch
    )

    # Create session manager for StreamableHTTP transport
    session_manager = StreamableHTTPSessionManager(
        app=server.app,
        event_store=None,  # Can be configured for resumability
        json_response=False,  # Use SSE streaming by default
        stateless=stateless_http,
    )

    # ASGI handler for streamable HTTP connections
    async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    # Lifespan context manager for proper startup/shutdown
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Context manager for managing session manager lifecycle."""
        async with session_manager.run():
            logger.info("Application started with StreamableHTTP session manager!")
            if enable_auto_update:
                logger.info("Starting auto-updater...")
                await server.start_auto_updater()
            try:
                yield
            finally:
                logger.info("Application shutting down...")
                if enable_auto_update:
                    logger.info("Stopping auto-updater...")
                    await server.stop_auto_updater()

    # Create Starlette app with StreamableHTTP transport
    app = Starlette(
        debug=True,
        routes=[
            Mount("/mcp", app=handle_streamable_http),
        ],
        lifespan=lifespan,
    )
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PyMilvus Code Generation Helper (Streamable HTTP Server)")
    parser.add_argument(
        "--milvus_uri", type=str, default="http://localhost:19530", help="Milvus server URI"
    )
    parser.add_argument("--milvus_token", type=str, default="", help="Milvus server token")
    parser.add_argument("--db_name", type=str, default="default", help="Milvus database name")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=23333, help="Port to run the server on")
    parser.add_argument(
        "--stateless_http", 
        action="store_true", 
        default=True,
        help="If True, uses true stateless mode (new transport per request)"
    )
    parser.add_argument(
        "--disable_auto_update", 
        action="store_true", 
        default=False,
        help="Disable automatic document updates"
    )
    parser.add_argument(
        "--update_interval",
        type=int,
        default=60,
        help="Document update interval in minutes (default: 60)"
    )

    args = parser.parse_args()

    app = create_app(
        milvus_uri=args.milvus_uri,
        milvus_token=args.milvus_token,
        db_name=args.db_name,
        stateless_http=args.stateless_http,
        enable_auto_update=not args.disable_auto_update,
        update_interval_minutes=args.update_interval
    )

    logger.info(f"Starting streamable HTTP server on {args.host}:{args.port}")
    logger.info(f"Stateless HTTP mode: {args.stateless_http}")
    logger.info(f"Auto-update enabled: {not args.disable_auto_update}")
    if not args.disable_auto_update:
        logger.info(f"Update interval: {args.update_interval} minutes")
    logger.info(f"MCP StreamableHTTP endpoint available at: http://{args.host}:{args.port}/mcp")
    
    uvicorn.run(app, host=args.host, port=args.port)