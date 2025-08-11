FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

# Set working directory inside the container
WORKDIR /app

# Install git and apt-utils (required for proper package installation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    apt-utils \
    && rm -rf /var/lib/apt/lists/*

# Install project dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --no-cache-dir

# Copy application source code and static assets
COPY src/ src/
COPY assets/ assets/

# Ensure logs are flushed immediately
ENV PYTHONUNBUFFERED=1

# Expose default HTTP port
EXPOSE 8000

# Start the FastMCP server (all credentials are provided via environment variables at runtime)
CMD ["sh", "-c", "uv run src/mcp_pymilvus_code_generate_helper/fastmcp_server.py --milvus_uri \"$MILVUS_URI\" --milvus_token \"$MILVUS_TOKEN\""]