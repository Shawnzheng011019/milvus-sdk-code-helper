import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

async def _stream_subprocess(cmd: list[str], cwd: Optional[Path] = None) -> int:
    """Run subprocess and stream its output line-by-line to the logger.

    Args:
        cmd: Command list, e.g. ["git", "clone", ...]
        cwd: Working directory.

    Returns:
        Process return code.
    """
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    percent_regex = re.compile(r"(\d{1,3})%")  # capture percentage value

    async def _pipe(reader: asyncio.StreamReader, tracker: dict):
        """Stream output, emitting progress lines at most once per 1% increment.

        The function accumulates data chunks into a buffer so that carriage-return
        based progress updates are handled correctly and each logical line is
        processed exactly once.
        """
        buffer: str = ""
        while True:
            chunk = await reader.read(1024)
            if not chunk:
                break
            # Git writes progress using carriage returns; convert to newlines for uniform handling
            buffer += chunk.decode(errors="ignore").replace("\r", "\n")
            *lines, buffer = buffer.split("\n")  # keep the last partial line in buffer
            for line in lines:
                _handle_line(line, tracker)

        # Process any remaining content in the buffer once the stream closes
        if buffer:
            _handle_line(buffer, tracker)

    def _handle_line(line: str, tracker: dict):
        """Handle a single line of git output with throttled progress logging."""
        line = line.strip()
        if not line:
            return

        match = percent_regex.search(line)
        if match:
            percent_val = int(match.group(1))
            # Detect stage reset (e.g., 100% of one phase, then 0% of next)
            if percent_val < tracker["last_percent"]:
                tracker["last_percent"] = -1
            if percent_val > tracker["last_percent"]:
                tracker["last_percent"] = percent_val
                logger.info(line)
        else:
            logger.info(line)

    # trackers for stdout and stderr respectively
    stdout_tracker = {"last_percent": -1}
    stderr_tracker = {"last_percent": -1}

    # Stream stdout/stderr concurrently
    stdout_task = asyncio.create_task(_pipe(process.stdout, stdout_tracker))
    stderr_task = asyncio.create_task(_pipe(process.stderr, stderr_tracker))

    await process.wait()
    await stdout_task
    await stderr_task
    return process.returncode

class GitRepoManager:
    """Manages Git repository operations for web-content updates"""
    
    def __init__(self, repo_url: str, local_path: str, branch: str = "master"):
        self.repo_url = repo_url
        self.local_path = Path(local_path)
        self.branch = branch
        self.last_commit_hash: Optional[str] = None
        
    async def ensure_repo_exists(self) -> bool:
        """Ensure the repository exists locally, clone if necessary"""
        try:
            if not self.local_path.exists():
                logger.info(f"Repository not found at {self.local_path}, cloning...")
                return await self._clone_repo()
            elif not (self.local_path / ".git").exists():
                logger.warning("Directory exists but is not a git repository, removing and cloning...")
                shutil.rmtree(self.local_path)
                return await self._clone_repo()
            else:
                logger.info(f"Repository already exists at {self.local_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to ensure repository exists: {e}")
            return False
    
    async def _clone_repo(self) -> bool:
        """Clone the repository"""
        try:
            self.local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Clone with progress so that git writes progress to stderr which we stream
            cmd = [
                "git",
                "clone",
                "--progress",
                "-b",
                self.branch,
                self.repo_url,
                str(self.local_path),
            ]

            rc = await _stream_subprocess(cmd)

            if rc == 0:
                logger.info(f"Successfully cloned repository to {self.local_path}")
                await self._update_last_commit_hash()
                return True
            else:
                logger.error("Failed to clone repository (see log for details)")
                return False
                
        except Exception as e:
            logger.error(f"Exception during repository cloning: {e}")
            return False
    
    async def check_for_updates(self) -> bool:
        """Check if there are updates available in the remote repository"""
        try:
            if not await self.ensure_repo_exists():
                return False
            
            # Fetch latest changes
            rc = await _stream_subprocess(
                ["git", "fetch", "--progress", "origin", self.branch], cwd=self.local_path
            )

            if rc != 0:
                logger.error("Failed to fetch updates (see log)")
                return False
            
            # Get remote commit hash
            remote_hash = await self._get_remote_commit_hash()
            current_hash = await self._get_current_commit_hash()
            
            if remote_hash and current_hash and remote_hash != current_hash:
                logger.info(f"Updates available: {current_hash[:8]} -> {remote_hash[:8]}")
                return True
            else:
                logger.info("No updates available")
                return False
                
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return False
    
    async def pull_updates(self) -> bool:
        """Pull the latest updates from the remote repository"""
        try:
            if not await self.ensure_repo_exists():
                return False
            
            # Reset any local changes
            rc = await _stream_subprocess(
                ["git", "reset", "--hard", f"origin/{self.branch}"], cwd=self.local_path
            )

            if rc != 0:
                logger.error("Failed to reset repository (see log)")
                return False
            
            # Pull latest changes
            rc = await _stream_subprocess(
                ["git", "pull", "--progress", "origin", self.branch], cwd=self.local_path
            )

            if rc == 0:
                logger.info("Successfully pulled latest updates")
                await self._update_last_commit_hash()
                return True
            else:
                logger.error("Failed to pull updates (see log)")
                return False
                
        except Exception as e:
            logger.error(f"Exception during repository update: {e}")
            return False
    
    async def _get_current_commit_hash(self) -> Optional[str]:
        """Get the current commit hash"""
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=self.local_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                logger.error(f"Failed to get current commit hash: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.error(f"Exception getting current commit hash: {e}")
            return None
    
    async def _get_remote_commit_hash(self) -> Optional[str]:
        """Get the remote commit hash"""
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "rev-parse", f"origin/{self.branch}",
                cwd=self.local_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                logger.error(f"Failed to get remote commit hash: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.error(f"Exception getting remote commit hash: {e}")
            return None
    
    async def _update_last_commit_hash(self):
        """Update the stored last commit hash"""
        self.last_commit_hash = await self._get_current_commit_hash()
    
    def get_docs_paths(self) -> dict:
        """Get the paths to different documentation directories by selecting latest versions."""
        version_regex = re.compile(r"^v(\d+)\.(\d+)\.x$")

        def _latest_subdir(parent: Path) -> Path | None:
            if not parent.exists():
                return None
            latest: tuple[int, int] | None = None
            latest_path: Path | None = None
            for child in parent.iterdir():
                if not child.is_dir():
                    continue
                m = version_regex.match(child.name)
                if not m:
                    continue
                ver = (int(m.group(1)), int(m.group(2)))
                if latest is None or ver > latest:
                    latest = ver
                    latest_path = child
            return latest_path

        base_path = self.local_path
        user_guide_version = _latest_subdir(base_path)
        pymilvus_version = _latest_subdir(base_path / "API_Reference" / "pymilvus")

        return {
            "user_guide": (user_guide_version / "site" / "en" / "userGuide") if user_guide_version else None,
            "orm_api": (pymilvus_version / "ORM") if pymilvus_version else None,
            "client_api": (pymilvus_version / "MilvusClient") if pymilvus_version else None,
            "multi_lang_api": base_path / "API_Reference"
        }
    
    def is_repo_ready(self) -> bool:
        """Check if the repository is ready for use"""
        docs = self.get_docs_paths()
        return (
            self.local_path.exists()
            and (self.local_path / ".git").exists()
            and any(p is not None and Path(p).exists() for p in docs.values())
        )
