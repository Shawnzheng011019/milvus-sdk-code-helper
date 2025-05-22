import argparse
import logging
from typing import Any, Sequence

import uvicorn
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool
from milvus_connector import MilvusConnector
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Scope, Receive, Send

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
    ):
        super().__init__(
            milvus_uri=milvus_uri, 
            milvus_token=milvus_token, 
            db_name=db_name,
            enable_auto_update=enable_auto_update,
            update_interval_minutes=update_interval_minutes
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
                                "description": "A string of Milvus API names in list format to translate from one programming language to another (e.g., ['create_collection', 'insert', 'search'])",
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


def create_app(
    milvus_uri="http://localhost:19530", 
    milvus_token="", 
    db_name="default", 
    stateless_http: bool = False,
    enable_auto_update=False,
    update_interval_minutes=60,
) -> Starlette:
    """Create a Starlette app with streamable HTTP transport."""
    server = McpServer(
        milvus_uri=milvus_uri, 
        milvus_token=milvus_token, 
        db_name=db_name,
        stateless_http=stateless_http,
        enable_auto_update=enable_auto_update,
        update_interval_minutes=update_interval_minutes,
    )
    
    # Create session manager with stateless_http parameter
    session_manager = StreamableHTTPSessionManager(
        app=server.app,
        stateless=stateless_http  # Use the stateless_http parameter
    )
    
    # Create ASGI handler for streamable HTTP
    async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)
    
    # Create routes
    routes = [
        Mount("/mcp", app=handle_streamable_http)
    ]

    app = Starlette(routes=routes)
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
    logger.info(f"MCP endpoint available at: http://{args.host}:{args.port}/mcp")
    
    uvicorn.run(app, host=args.host, port=args.port)
