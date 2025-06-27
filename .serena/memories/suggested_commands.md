## 常用开发命令

1. 安装依赖（使用 uv 推荐）
   ```bash
   uv pip install -r pyproject.toml
   ```

2. 运行 SSE MCP Server
   ```bash
   uv run src/mcp_pymilvus_code_generate_helper/sse_server.py
   ```

3. 运行 STDIO MCP Server
   ```bash
   uv run src/mcp_pymilvus_code_generate_helper/stdio_server.py
   ```

4. 本地格式化代码（写入变更）
   ```bash
   ruff format .
   ```

5. 检查代码格式（不会修改文件）
   ```bash
   ruff format --check .
   ```

6. Lint 检查
   ```bash
   ruff check .
   ```

7. 构建并运行 Docker 镜像
   ```bash
   docker build -t milvus-code-helper .
   docker run -p 23333:23333 -e OPENAI_API_KEY=<key> milvus-code-helper
   ```