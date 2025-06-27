## [Unreleased] - 2025-06-26
### Added
- Introduced `doc_updater.py`: synchronous pipeline that deletes previous `./web-content` repo, clones latest documentation, drops existing Milvus collections, embeds docs with OpenAI, and uploads them.
- Introduced `scheduler.py`: light-weight weekly background thread executing the refresh pipeline, fully decoupled from FastMCP runtime.
- Introduced detailed logging: git clone and embedding stages now stream to both stdout and time-stamped files under `./logs/`. This uses a dual-handler `logging.basicConfig` and captures stdout/stderr from embedding scripts.
- Added `fastmcp` runtime dependency and CLI entry point `pymilvus-helper` via `project.scripts` in `pyproject.toml`.
- Dockerfile: Added support for injecting `OPENAI_API_KEY` via build argument and runtime environment variable.

### Changed
- `fastmcp_server.py` now runs `update_documents()` once during startup and launches the weekly scheduler; removed all async `DocumentAutoUpdater` logic and command-line flags `--enable_auto_update`, `--update_interval`.
- `milvus_connector.py` simplified; all references to `DocumentAutoUpdater` removed.
- `doc_updater.update_documents()` now purges leftover embedding CSV files (`embeddings_temp.csv`, `MilvusClient_embeddings.csv`, `multi_language_docs_with_embedding.csv`, `ORM_embeddings.csv`, `userGuide_embeddings.csv`) before cloning the documentation repository to guarantee a clean state for each run.
- Rewritten `Dockerfile` to install dependencies using `uv.lock`, copy static assets, expose port `8000`, and improve layer caching.
- Codebase formatting and linting cleanup: reorganized imports, removed unused imports, fixed duplicate imports, corrected f-string placeholder, and added `# noqa: E402` where dynamic path tweaks precede imports to ensure Ruff passes with no errors.

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