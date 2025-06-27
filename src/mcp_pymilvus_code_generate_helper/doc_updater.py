#!/usr/bin/env python3
"""doc_updater.py

Synchronous utilities to (1) clone documentation repository, (2) rebuild OpenAI
embeddings, and (3) upload collections to Milvus. Designed to be called in a
blocking fashion during first boot, and later from a background scheduler once
per week.

The functions here purposely avoid async/await so that callers do not have to
manage event loops.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List

# Add scripts/load_doc to import path for document processing helpers


BASE_DIR = Path(__file__).parent.parent
SCRIPT_LOAD_DOC_PATH = BASE_DIR / "scripts" / "load_doc"
sys.path.append(str(SCRIPT_LOAD_DOC_PATH))

# Import helper to stream git progress with percentage
from git_repo_manager import _stream_subprocess  # noqa: E402

# Re-use the existing ingestion utilities living under scripts/load_doc (imported after path tweak)
from process_docs_to_milvus import process_docs_to_milvus  # type: ignore  # noqa: E402
from process_multi_language_docs_2_vector_db import (  # type: ignore  # noqa: E402
    main as process_multi_language_docs,
)
from pymilvus import MilvusClient  # noqa: E402

# Logging configuration ----------------------------------------------------

LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"update_{int(time.time())}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)

REPO_URL = "https://github.com/milvus-io/web-content.git"
REPO_BRANCH = "master"
LOCAL_REPO_PATH = Path("./web-content")

# Milvus collections managed by this helper
COLLECTIONS: List[str] = [
    "pymilvus_user_guide",
    "mcp_orm",
    "mcp_milvus_client",
    "mcp_multi_language_docs",
]

# NEW: list of embedding CSV files that should be removed before each refresh
EMBEDDING_CSV_FILES: List[str] = [
    "embeddings_temp.csv",
    "MilvusClient_embeddings.csv",
    "multi_language_docs_with_embedding.csv",
    "ORM_embeddings.csv",
    "userGuide_embeddings.csv",
]

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a subprocess, streaming output, and raise on failure."""
    logger.info("$ %s", " ".join(cmd))
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert process.stdout is not None
    for line in process.stdout:
        logger.info(line.rstrip())
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"Command failed with code {process.returncode}: {' '.join(cmd)}")


def _safe_rmtree(path: Path) -> None:
    if path.exists():
        logger.info("Removing directory %s", path)
        shutil.rmtree(path)


def _git_clone() -> None:
    cmd = [
        "git",
        "clone",
        "--progress",
        "-b",
        REPO_BRANCH,
        REPO_URL,
        str(LOCAL_REPO_PATH),
    ]

    # _stream_subprocess is async, run it synchronously here
    rc = asyncio.run(_stream_subprocess(cmd))
    if rc != 0:
        raise RuntimeError(f"git clone failed with exit code {rc}")

# ---------------------------------------------------------------------------
# Milvus helpers
# ---------------------------------------------------------------------------

def _cleanup_collections(client: MilvusClient) -> None:
    for name in COLLECTIONS:
        try:
            if client.has_collection(name):
                logger.info("Dropping existing collection %s", name)
                client.drop_collection(name)
            else:
                logger.info("Collection %s does not exist – skip drop", name)
        except Exception as exc:
            logger.warning("Failed to drop collection %s: %s", name, exc)


# ---------------------------------------------------------------------------
# Embedding ingestion
# ---------------------------------------------------------------------------

def _embed_user_guide(base: Path, client: MilvusClient, uri: str, token: str):
    path = base / "v2.5.x" / "site" / "en" / "userGuide"
    if path.exists():
        logger.info("Processing user guide documents: %s", path)
        _run_with_capture(
            process_docs_to_milvus,
            str(path),
            uri,
            token,
            "pymilvus_user_guide",
            "userGuide_embeddings.csv",
        )
    else:
        logger.warning("User guide directory not found: %s", path)


def _embed_orm_api(base: Path, client: MilvusClient, uri: str, token: str):
    path = base / "API_Reference" / "pymilvus" / "v2.5.x" / "ORM"
    if path.exists():
        logger.info("Processing ORM API documents: %s", path)
        _run_with_capture(
            process_docs_to_milvus,
            str(path),
            uri,
            token,
            "mcp_orm",
            "ORM_embeddings.csv",
        )
    else:
        logger.warning("ORM API directory not found: %s", path)


def _embed_client_api(base: Path, client: MilvusClient, uri: str, token: str):
    path = base / "API_Reference" / "pymilvus" / "v2.5.x" / "MilvusClient"
    if path.exists():
        logger.info("Processing MilvusClient API documents: %s", path)
        _run_with_capture(
            process_docs_to_milvus,
            str(path),
            uri,
            token,
            "mcp_milvus_client",
            "MilvusClient_embeddings.csv",
        )
    else:
        logger.warning("MilvusClient API directory not found: %s", path)


def _embed_multi_language(base: Path, client: MilvusClient, uri: str, token: str):
    multi_lang_base = base / "API_Reference"
    if not multi_lang_base.exists():
        logger.warning("Multi-language API directory not found: %s", multi_lang_base)
        return

    logger.info("Processing multi-language API documents: %s", multi_lang_base)

    # process_multi_language_docs uses argparse; patch sys.argv for compatibility
    original_argv = sys.argv.copy()
    sys.argv = [
        "process_multi_language_docs_2_vector_db.py",
        "--base-dir",
        str(multi_lang_base),
        "--collection",
        "mcp_multi_language_docs",
        "--output-csv",
        "multi_language_docs_with_embedding.csv",
        "--milvus-uri",
        uri,
        "--milvus-token",
        token,
    ]
    try:
        _run_with_capture(process_multi_language_docs)
    finally:
        sys.argv = original_argv


# ---------------------------------------------------------------------------
# Public API – single entry point
# ---------------------------------------------------------------------------

def update_documents(milvus_uri: str, milvus_token: str) -> None:
    """Run the full 1-4 document refresh pipeline.

    1. Remove existing local repo directory
    2. Clone the specified branch of web-content repo
    3. Drop existing Milvus collections (if any)
    4. Re-embed documents and upload collections
    """

    start_ts = time.time()
    logger.info("Starting full documentation refresh …")

    # NEW: remove any previously generated embedding CSV files
    _purge_old_embedding_files()

    # 1. remove old repo
    _safe_rmtree(LOCAL_REPO_PATH)

    # 2. git clone
    _git_clone()

    # 3. cleanup collections
    client = MilvusClient(uri=milvus_uri, token=milvus_token)
    _cleanup_collections(client)

    # 4. embed and upload
    base = LOCAL_REPO_PATH
    _embed_user_guide(base, client, milvus_uri, milvus_token)
    _embed_orm_api(base, client, milvus_uri, milvus_token)
    _embed_client_api(base, client, milvus_uri, milvus_token)
    _embed_multi_language(base, client, milvus_uri, milvus_token)

    elapsed = time.time() - start_ts
    logger.info("Documentation refresh completed in %.1f s", elapsed)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _run_with_capture(func, *args, **kwargs):
    """Run *func* capturing stdout/stderr and forwarding to logger."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        func(*args, **kwargs)
    for line in buf.getvalue().splitlines():
        logger.info(line)

def _purge_old_embedding_files() -> None:
    """Delete leftover embedding CSV files from previous runs."""
    for fname in EMBEDDING_CSV_FILES:
        path = Path(fname)
        if path.exists():
            try:
                path.unlink()
                logger.info("Removed stale embedding file %s", path)
            except Exception as exc:
                logger.warning("Failed to remove file %s: %s", path, exc)
        else:
            logger.debug("Embedding file %s does not exist – skip", path) 