FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

# Accept OpenAI API key during build (optional; can be overridden at runtime)
ARG OPENAI_API_KEY

# Set working directory inside the container
WORKDIR /app

# Install git (required for runtime document cloning)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install project dependencies first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --no-cache-dir

# Copy application source code and static assets
COPY src/ src/
COPY assets/ assets/

# Ensure logs are flushed immediately
ENV PYTHONUNBUFFERED=1

# Pass OpenAI API key to the runtime environment (leave empty if not provided at build/run time)
ENV OPENAI_API_KEY=$OPENAI_API_KEY

# Expose default HTTP port
EXPOSE 8000

# Start the FastMCP server (Milvus credentials are provided via environment variables)
CMD uv run src/mcp_pymilvus_code_generate_helper/fastmcp_server.py --milvus_uri "$MILVUS_URI" --milvus_token "$MILVUS_TOKEN"