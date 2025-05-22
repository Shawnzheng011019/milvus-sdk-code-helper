import asyncio
import re
import sys
from contextlib import AsyncExitStack
from typing import Optional

from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

QUERY_PROMPT = """
Use your tools to retrieve the most relevant information from the given query.

Query:
{query}
"""


class MCPClient:
    def __init__(
        self,
        server_script_path: str,
        model_name: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 1000,
    ):
        # Initialize session and client objects
        self.server_script_path = server_script_path
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.model_name = model_name
        self.max_tokens = max_tokens

    async def connect_to_server(self):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = self.server_script_path.endswith(".py")
        if not is_python:
            raise ValueError("Server script must be a .py file")

        command = sys.executable
        server_params = StdioServerParameters(
            command=command, args=[self.server_script_path], env=None
        )

        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.stdio, self.write)
            )

            await self.session.initialize()

            # List available tools
            response = await self.session.list_tools()
            tools = response.tools
            print("\nConnected to server with tools:", [tool.name for tool in tools])
        except Exception as e:
            await self.exit_stack.aclose()
            raise e

    async def retrieve(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        messages = [{"role": "user", "content": QUERY_PROMPT.format(query=query)}]

        response = await self.session.list_tools()
        available_tools = [
            {"name": tool.name, "description": tool.description, "input_schema": tool.inputSchema}
            for tool in response.tools
        ]

        response = self.anthropic.messages.create(
            model=self.model_name,
            max_tokens=self.max_tokens,
            messages=messages,
            tools=available_tools,
        )

        retrieved_file_names = []
        for content in response.content:
            if content.type == "text":
                print("content.type:", content.type)
                print("content:", content)
                print("The tool using is not triggered, consider how to handle it")
                pass  # TODO: the tool using is not triggered, consider how to handle it
            elif content.type == "tool_use":
                print("content.type:", content.type)
                tool_name = content.name
                tool_args = content.input
                print("tool_name, tool_args:", tool_name, tool_args)

                result = await self.session.call_tool(tool_name, tool_args)
                print(f"Tool call result: {result}")

                # Find all markdown file names in the result
                if result and hasattr(result, "content"):
                    text_content = (
                        result.content[0].text
                        if result.content and isinstance(result.content[0], TextContent)
                        else ""
                    )
                    # Match file names in format like "1 (File: xxx.md):"
                    markdown_files = re.findall(r"\(File: ([a-zA-Z0-9_\-]+\.md)\)", text_content)
                    retrieved_file_names.extend(markdown_files)

        return retrieved_file_names

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.retrieve(query)
                print(response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    client = MCPClient(
        server_script_path="/Users/zilliz/Documents/GitHub/mcp-pymilvus-code-generator/src/mcp_pymilvus_code_generate_helper/stdio_server.py"
    )

    try:
        await client.connect_to_server()
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
