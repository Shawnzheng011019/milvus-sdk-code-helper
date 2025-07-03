## [Unreleased] - 2025-01-07
### Changed
- **Major README.md restructure**: Completely rewrote README.md to focus on FastMCP as the primary usage mode, removed User Rule section, and reorganized content structure.
- **Enhanced FastMCP documentation**: Added comprehensive documentation for two distinct FastMCP server modes:
  - First-time setup using `src/mcp_pymilvus_code_generate_helper/fastmcp_server.py` (with automatic document update)
  - Subsequent runs using `examples/fastmcp_server.py` (lightweight mode without document sync)
- **Improved configuration guidance**: Added detailed configuration examples for HTTP, SSE, and STDIO transport modes with both Cursor and Claude Desktop.
- **Enhanced tool documentation**: Provided clear descriptions of all three tools with usage examples and parameter specifications.
- **Added troubleshooting section**: Included common issues, debug mode instructions, and configuration troubleshooting.
- **Updated Docker support**: Enhanced Docker documentation with FastMCP-specific examples and legacy transport mode support.

### Removed
- **User Rule section**: Removed the extensive User Rule configuration section from README.md as requested, simplifying the documentation.

## [Previous] - 2025-01-07
### Added
- Implemented intelligent exponential backoff retry mechanism for OpenAI embedding API calls. Added `retry_decorator.py` with configurable retry logic including exponential backoff, jitter to prevent thundering herd effects, and differentiated handling of retryable vs non-retryable exceptions.
- Applied smart retry decorator to all OpenAI embedding API calls across:
  - `md_2_embedding.py`: Basic document embedding generation
  - `process_multi_language_docs_2_vector_db.py`: Multi-language document processing  
  - `milvus_connector.py`: Real-time query embedding generation
- Retry configuration: 5 max retries, 2-second base delay, 120-second max delay, 20% jitter ratio for optimal network resilience.

### Fixed
- Removed duplicate document update execution during Docker container startup. Previously, the fastmcp_server.py would run update_documents() both synchronously at startup and immediately through the weekly scheduler, causing the documentation refresh pipeline to execute twice. Now only the scheduler-based update runs, eliminating redundant processing.
- Enhanced network resilience for OpenAI API calls with smart retry mechanism to handle connection timeouts, network interruptions, and temporary service unavailability.

## [2025-06-26]
### Added
- Introduced `doc_updater.py`: synchronous pipeline that deletes previous `./web-content` repo, clones latest documentation, drops existing Milvus collections, embeds docs with OpenAI, and uploads them.
- Introduced `scheduler.py`: light-weight weekly background thread executing the refresh pipeline, fully decoupled from FastMCP runtime.
- Introduced detailed logging: git clone and embedding stages now stream to both stdout and time-stamped files under `./logs/`. This uses a dual-handler `logging.basicConfig` and captures stdout/stderr from embedding scripts.
- Added `fastmcp` runtime dependency and CLI entry point `pymilvus-helper` via `project.scripts` in `pyproject.toml`.
- Dockerfile: Added support for injecting `OPENAI_API_KEY` via build argument and runtime environment variable.
- Added `examples/fastmcp_server.py`: lightweight FastMCP server variant that skips document synchronization and the weekly scheduler for faster startup when Milvus collections already exist.

### Changed
- `fastmcp_server.py` now runs `update_documents()` once during startup and launches the weekly scheduler; removed all async `DocumentAutoUpdater` logic and command-line flags `--enable_auto_update`, `--update_interval`.
- `milvus_connector.py` simplified; all references to `DocumentAutoUpdater` removed.
- `doc_updater.update_documents()` now purges leftover embedding CSV files (`embeddings_temp.csv`, `MilvusClient_embeddings.csv`, `multi_language_docs_with_embedding.csv`, `ORM_embeddings.csv`, `userGuide_embeddings.csv`) before cloning the documentation repository to guarantee a clean state for each run.
- Rewritten `Dockerfile` to install dependencies using `uv.lock`, copy static assets, expose port `8000`, and improve layer caching.
- Codebase formatting and linting cleanup: reorganized imports, removed unused imports, fixed duplicate imports, corrected f-string placeholder, and added `# noqa: E402` where dynamic path tweaks precede imports to ensure Ruff passes with no errors.
- `examples/fastmcp_server.py` now embeds its own `create_app` implementation and no longer depends on `mcp_pymilvus_code_generate_helper.fastmcp_server`.
- `examples/fastmcp_server.py` tool definitions (docstrings & guidance prompt) are now **identical** to those in `src/mcp_pymilvus_code_generate_helper/fastmcp_server.py` to ensure consistent behavior.

### Removed
- Deprecated async `DocumentAutoUpdater`

### Fixed
- Launch `DocumentAutoUpdater` in a dedicated background thread to ensure it runs independently of FastMCP's internal event loop. This resolves the issue where collections were never created/loaded and `collection not found` errors were thrown at startup.
- Prevent concurrent document processing by introducing a cross-thread lock in `DocumentAutoUpdater`. This avoids connection/handshake failures when multiple threads attempt to insert embeddings into Milvus simultaneously.

### Changed
- Server now performs a blocking initial documentation sync (clone and collection check) before starting, ensuring collections are ready when the HTTP endpoint becomes available.
- Git progress logging is now throttled: progress lines are emitted only when the percentage increases by at least 1%, significantly reducing log verbosity during clone, fetch, and pull operations.

### Added
- Git progress logging now updates in real time; lines are emitted when the progress percentage increases by at least 1%, ensuring smooth incremental output instead of a single burst at 100%.