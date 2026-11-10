"""
Repository ingestion.

Responsible for turning a GitHub URL into a local checkout and a flat
list of text-bearing files (source code + docs), skipping anything
that would be noise for retrieval (binaries, build output, lockfiles,
vendored dependencies, VCS internals).
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import os
import re
import shutil
import stat
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import git
import httpx

from app.config import get_settings

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", "__pycache__",
    ".next", ".venv", "venv", "env", "vendor", "target", ".cache",
    "coverage", ".idea", ".vscode", "egg-info",
}

SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "Cargo.lock",
}

SKIP_SUFFIXES = {
    ".lock", ".min.js", ".min.css", ".map", ".png", ".jpg", ".jpeg",
    ".gif", ".svg", ".ico", ".pdf", ".zip", ".tar", ".gz", ".woff",
    ".woff2", ".ttf", ".eot", ".mp4", ".mov", ".bin", ".exe", ".so",
    ".dylib", ".dll", ".pyc", ".class", ".jar", ".ipynb", ".csv",
    ".tsv", ".parquet", ".jsonl", ".pkl", ".h5",
}

LANGUAGE_BY_EXT = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go",
    ".rs": "rust", ".java": "java", ".rb": "ruby", ".php": "php",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp",
    ".md": "markdown", ".mdx": "markdown", ".rst": "text", ".txt": "text",
    ".yml": "yaml", ".yaml": "yaml", ".json": "json", ".toml": "toml",
}

MAX_FILE_BYTES = 400_000  # skip anything larger — unlikely to be hand-written source


@dataclass
class RepoFile:
    path: str          # relative path, POSIX style
    language: str
    content: str


def repo_id_for(url: str, branch: str | None) -> str:
    key = f"{url.strip().rstrip('/')}@{branch or ''}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def parse_repo_name(url: str) -> str:
    match = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url)
    if not match:
        return url
    return f"{match.group(1)}/{match.group(2)}"


class RepoValidationError(RuntimeError):
    """Raised when a repository URL doesn't point at something clonable."""


def validate_repo(url: str, branch: str | None) -> dict:
    """
    Checks the repo exists and is reachable *before* attempting a clone —
    this is the "Repository valid and accessible?" decision in the
    proposed workflow, so an invalid URL fails fast with a clear reason
    instead of surfacing as an opaque git error.
    """
    match = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url.strip())
    if not match:
        raise RepoValidationError("That doesn't look like a github.com repository URL.")

    owner, name = match.group(1), match.group(2)
    settings = get_settings()
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    try:
        resp = httpx.get(f"https://api.github.com/repos/{owner}/{name}", headers=headers, timeout=10)
    except httpx.HTTPError as exc:
        raise RepoValidationError(f"Could not reach GitHub to verify the repository: {exc}") from exc

    if resp.status_code == 404:
        raise RepoValidationError(
            f"'{owner}/{name}' was not found, or is private and GITHUB_TOKEN isn't set."
        )
    if resp.status_code == 403:
        raise RepoValidationError("GitHub API rate limit hit while validating. Set GITHUB_TOKEN and retry.")
    if resp.status_code != 200:
        raise RepoValidationError(f"GitHub returned {resp.status_code} while validating this repository.")

    data = resp.json()
    if branch:
        branch_resp = httpx.get(
            f"https://api.github.com/repos/{owner}/{name}/branches/{branch}", headers=headers, timeout=10
        )
        if branch_resp.status_code == 404:
            raise RepoValidationError(f"Branch '{branch}' does not exist on {owner}/{name}.")

    return {
        "full_name": data.get("full_name", f"{owner}/{name}"),
        "default_branch": data.get("default_branch", "main"),
        "private": data.get("private", False),
        "size_kb": data.get("size", 0),
    }


def safe_rmtree(path: Path) -> None:
    if not path.exists():
        return
    def _onerror(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    try:
        shutil.rmtree(path, onexc=lambda func, p, exc: (os.chmod(p, stat.S_IWRITE), func(p)))
    except (TypeError, Exception):
        try:
            shutil.rmtree(path, onerror=_onerror)
        except Exception:
            pass


def clone_repo(url: str, branch: str | None, repo_id: str, timeout_seconds: int = 30) -> Path:
    settings = get_settings()
    dest = settings.repos_dir / repo_id
    safe_rmtree(dest)

    clone_kwargs = {
        "depth": 1,
        "env": {"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo"},
    }
    if branch:
        clone_kwargs["branch"] = branch

    clone_url = url
    token = settings.github_token
    if token and clone_url.startswith("https://"):
        clone_url = clone_url.replace("https://", f"https://x-access-token:{token}@", 1)

    def _run_clone():
        repo = git.Repo.clone_from(clone_url, dest, **clone_kwargs)
        repo.close()
        return dest

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_clone)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            safe_rmtree(dest)
            raise TimeoutError(f"git clone timed out after {timeout_seconds}s")


def fetch_tarball(owner: str, name: str, branch: str, repo_id: str) -> Path:
    """
    Fallback ingestion path used when `git clone` fails or times out.
    Downloads compressed archive directly from GitHub over HTTPS and extracts it.
    """
    settings = get_settings()
    dest = settings.repos_dir / repo_id
    safe_rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    # First attempt: direct GitHub zip archive (fast, compressed, no rate limit)
    zip_url = f"https://github.com/{owner}/{name}/archive/refs/heads/{branch}.zip"
    try:
        with httpx.stream("GET", zip_url, headers=headers, timeout=60, follow_redirects=True) as resp:
            if resp.status_code == 200:
                buf = io.BytesIO()
                for chunk in resp.iter_bytes():
                    buf.write(chunk)
                buf.seek(0)
                with zipfile.ZipFile(buf, "r") as zf:
                    root_prefix = zf.namelist()[0].split("/")[0] + "/" if zf.namelist() else ""
                    for member in zf.infolist():
                        if not member.filename.startswith(root_prefix) or member.is_dir():
                            continue
                        rel = member.filename[len(root_prefix):]
                        if not rel or rel.startswith("..") or rel.startswith("/"):
                            continue
                        target = dest / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                return dest
    except Exception:
        pass

    # Second attempt: GitHub REST API tarball
    url = f"https://api.github.com/repos/{owner}/{name}/tarball/{branch}"
    buffer = None
    for attempt in range(3):
        try:
            with httpx.stream("GET", url, headers=headers, timeout=120, follow_redirects=True) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f"Tarball download failed ({resp.status_code}) for {owner}/{name}@{branch}")
                buf = io.BytesIO()
                for chunk in resp.iter_bytes():
                    buf.write(chunk)
                buf.seek(0)
                buffer = buf
                break
        except Exception:
            if attempt == 2:
                raise
    if buffer is None:
        raise RuntimeError(f"Failed to fetch archive after retries for {owner}/{name}@{branch}")

    with tarfile.open(fileobj=buffer, mode="r:gz") as tar:
        members = tar.getmembers()
        root_prefix = members[0].name.split("/")[0] + "/" if members else ""
        safe_members = []
        for m in members:
            if not m.name.startswith(root_prefix):
                continue
            rel = m.name[len(root_prefix):]
            if not rel or rel.startswith("..") or rel.startswith("/"):
                continue
            m.name = rel
            safe_members.append(m)
        tar.extractall(path=dest, members=safe_members)

    return dest


def clone_or_fetch(url: str, branch: str | None, repo_id: str, owner: str, name: str,
                    default_branch: str) -> tuple[Path, bool]:
    """
    Tries the fast path (shallow git clone) first; on any failure, falls
    back to the GitHub tarball API. Returns (checkout_path, used_fallback).
    """
    try:
        return clone_repo(url, branch, repo_id), False
    except Exception:
        ref = branch or default_branch
        return fetch_tarball(owner, name, ref, repo_id), True


def default_branch_of(dest: Path) -> str:
    repo = git.Repo(dest)
    try:
        try:
            return repo.active_branch.name
        except TypeError:
            return repo.git.rev_parse("--abbrev-ref", "HEAD")
    finally:
        repo.close()


def walk_repo_files(dest: Path) -> list[RepoFile]:
    files: list[RepoFile] = []
    for path in dest.rglob("*"):
        if not path.is_file():
            continue
        if path.name in SKIP_FILES or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue

        language = LANGUAGE_BY_EXT.get(path.suffix.lower())
        if language is None:
            # Unknown extension: only keep it if it decodes cleanly as text
            # and isn't suspiciously binary-looking.
            language = "text"

        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        if not content.strip():
            continue

        rel = path.relative_to(dest).as_posix()
        files.append(RepoFile(path=rel, language=language, content=content))

    return files


def build_file_tree(paths: list[str]) -> dict:
    """
    Turns a flat list of indexed file paths into a nested tree the
    frontend can render as a collapsible structure — this is what backs
    the "understands file structure" feature: a repo map, not just a
    bag of retrievable chunks.
    """
    root: dict = {"name": "", "type": "dir", "children": {}}
    for p in sorted(paths):
        parts = p.split("/")
        node = root
        for i, part in enumerate(parts):
            is_file = i == len(parts) - 1
            children = node["children"]
            if part not in children:
                children[part] = (
                    {"name": part, "type": "file", "path": p}
                    if is_file
                    else {"name": part, "type": "dir", "children": {}}
                )
            node = children[part]

    def to_list(n: dict) -> dict:
        if n["type"] == "file":
            return {"name": n["name"], "type": "file", "path": n["path"]}
        kids = [to_list(c) for c in n["children"].values()]
        kids.sort(key=lambda k: (k["type"] != "dir", k["name"].lower()))
        return {"name": n["name"], "type": "dir", "children": kids}

    return to_list(root)


def render_tree_text(tree: dict, max_lines: int = 160) -> str:
    """
    Flattens the nested tree into an indented text listing, capped at
    ``max_lines``. This is what actually answers "what's the file
    structure?" — the model sees the real layout, not just whatever
    chunks happened to rank highest for that query.
    """
    lines: list[str] = []

    def walk(node: dict, depth: int) -> None:
        if len(lines) >= max_lines:
            return
        if node["type"] == "file":
            lines.append("  " * depth + node["name"])
            return
        label = node["name"] or "/"
        if depth >= 0:
            lines.append("  " * depth + label + "/")
        for child in node.get("children", []):
            if len(lines) >= max_lines:
                lines.append("  " * (depth + 1) + "…")
                return
            walk(child, depth + 1)

    for child in tree.get("children", []):
        walk(child, 0)

    return "\n".join(lines[:max_lines])
