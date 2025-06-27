## 项目概述

mcp-pymilvus-code-generate-helper 是一个基于 Model Context Protocol (MCP) 的服务，用于检索与生成 Milvus Python SDK（pymilvus）代码片段与文档，从而辅助 LLM 编写或转换 Milvus 代码。它支持 SSE、STDIO 等多种通信方式，并可部署为独立 FastMCP 服务器或通过 Docker 运行。

主要组件：
1. `milvus_connector.py`：连接本地或远程 Milvus 实例，执行向量检索。
2. `sse_server.py` / `stdio_server.py` / `streamable_http_server.py`：不同通信协议的 MCP 服务器实现。
3. `fastmcp_server.py`：基于 fastapi/starlette 的 HTTP Server 版本。
4. `scheduler.py`：任务调度与缓存。
5. `doc_updater.py`：将新文档解析并插入向量数据库（Milvus）。

典型工作流：
LLM 收到用户对 pymilvus 代码的需求 → 调用 MCP 服务 → MCP 服务在向量库中检索相关文档/代码 → 返回结果帮助生成代码。