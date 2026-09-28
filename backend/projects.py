"""Small disk-backed project store for the local builder."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

def configured_projects_root() -> Path:
    if directory := os.getenv("PROJECTS_DIR"):
        return Path(directory).expanduser().resolve()
    if os.getenv("VERCEL") == "1":
        # The deployment filesystem is read-only; this storage is ephemeral.
        return Path(tempfile.gettempdir()) / "jenga" / "generated_projects"
    return Path(__file__).resolve().parents[1] / "generated_projects"


PROJECTS_ROOT = configured_projects_root()


def project_dir(project_id: str) -> Path:
    return PROJECTS_ROOT / str(UUID(project_id))


def load_project(project_id: str) -> dict:
    return json.loads((project_dir(project_id) / "project.json").read_text(encoding="utf-8"))


def save_project(project: dict) -> None:
    root = project_dir(project["id"])
    root.mkdir(parents=True, exist_ok=True)
    project["updated_at"] = datetime.now(timezone.utc).isoformat()
    temporary = root / "project.json.tmp"
    temporary.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, root / "project.json")


def read_files(project_id: str) -> dict[str, str]:
    root = project_dir(project_id) / "files"
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            continue
        if path.stat().st_size > 1_000_000:
            continue
        try:
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return files
