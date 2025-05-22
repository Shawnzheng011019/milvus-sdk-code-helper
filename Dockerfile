FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

WORKDIR /app

COPY pyproject.toml .
RUN uv sync

COPY src/ src/

CMD uv run src/mcp_pymilvus_code_generate_helper/sse_server.py --milvus_uri "$MILVUS_URI" --milvus_token "$MILVUS_TOKEN"
