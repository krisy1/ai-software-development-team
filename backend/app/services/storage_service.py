from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
CHECKPOINTS_DIR = STORAGE_DIR / "checkpoints"
BACKUPS_DIR = STORAGE_DIR / "backups"
GENERATED_CODE_DIR = STORAGE_DIR / "generated_code"
MANIFESTS_DIR = STORAGE_DIR / "manifests"
LOGS_DIR = STORAGE_DIR / "logs"


class StorageService:
    """File-system persistence for checkpoints, backups, and generated code.

    Provides automatic versioning with a configurable retention policy.
    All paths are relative to the project's ``storage/`` directory.
    """

    def __init__(self) -> None:
        self._ensure_dirs()

    # ── Directory setup ───────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        for d in (CHECKPOINTS_DIR, BACKUPS_DIR, GENERATED_CODE_DIR, MANIFESTS_DIR, LOGS_DIR):
            d.mkdir(parents=True, exist_ok=True)

    # ── Checkpoints ───────────────────────────────────────────────

    def save_checkpoint(
        self,
        project_id: str,
        state: dict[str, Any],
        description: str = "",
    ) -> Path:
        """Save a checkpoint of the current pipeline state to disk.

        Checkpoints are stored as ``checkpoints/{project_id}_{timestamp}.json``
        and contain the full GraphState plus metadata.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{project_id}_{timestamp}.json"
        path = CHECKPOINTS_DIR / filename

        checkpoint = {
            "project_id": project_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "description": description,
            "state": {
                k: v
                for k, v in state.items()
                if k not in ("agent_results", "token_usage", "errors", "warnings")
            },
            "token_usage": state.get("token_usage", []),
            "errors": state.get("errors", []),
            "warnings": state.get("warnings", []),
        }

        path.write_text(json.dumps(checkpoint, indent=2, default=str))
        logger.info(
            "checkpoint_saved",
            project_id=project_id,
            path=str(path),
            size=path.stat().st_size,
        )
        return path

    def load_checkpoint(self, path: Path) -> dict[str, Any]:
        """Load a checkpoint from disk."""
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {path}")
        return json.loads(path.read_text())

    def list_checkpoints(self, project_id: Optional[str] = None) -> list[Path]:
        """List all checkpoints, optionally filtered by project_id."""
        paths = sorted(CHECKPOINTS_DIR.glob("*.json"), reverse=True)
        if project_id:
            paths = [p for p in paths if p.stem.startswith(project_id)]
        return paths

    # ── Backups ───────────────────────────────────────────────────

    def create_backup(self, name: str = "") -> Path:
        """Create a timestamped ZIP backup of the project state.

        Archives: checkpoints, generated_code, manifests, and the
        current project_manifest.json.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        label = f"{name}_{timestamp}" if name else timestamp
        backup_path = BACKUPS_DIR / f"backup_{label}.zip"

        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for directory in (CHECKPOINTS_DIR, GENERATED_CODE_DIR, MANIFESTS_DIR):
                for file_path in directory.rglob("*"):
                    if file_path.is_file():
                        zf.write(file_path, file_path.relative_to(STORAGE_DIR))

            manifest = PROJECT_ROOT / "project_manifest.json"
            if manifest.exists():
                zf.write(manifest, manifest.relative_to(PROJECT_ROOT))

        logger.info("backup_created", path=str(backup_path))
        return backup_path

    # ── Generated code persistence ────────────────────────────────

    def save_generated_code(
        self,
        project_id: str,
        files: list[dict[str, str]],
        revision: int = 1,
    ) -> Path:
        """Persist generated source code to disk as individual files.

        Maintains a directory per project_id under ``generated_code/``:
        ``generated_code/{project_id}/rev_{revision}/src/...``
        """
        rev_dir = GENERATED_CODE_DIR / project_id / f"rev_{revision}"
        rev_dir.mkdir(parents=True, exist_ok=True)

        for entry in files:
            file_path = rev_dir / entry["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(entry.get("content", ""))

        logger.info(
            "generated_code_saved",
            project_id=project_id,
            revision=revision,
            file_count=len(files),
            target=str(rev_dir),
        )
        return rev_dir

    def load_generated_code(
        self,
        project_id: str,
        revision: int = 1,
    ) -> list[dict[str, str]]:
        """Load previously generated code from disk."""
        rev_dir = GENERATED_CODE_DIR / project_id / f"rev_{revision}"
        if not rev_dir.exists():
            return []

        files: list[dict[str, str]] = []
        for file_path in sorted(rev_dir.rglob("*")):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(rev_dir))
                files.append({
                    "path": rel_path,
                    "content": file_path.read_text(),
                    "language": rel_path.rsplit(".", 1)[-1] if "." in rel_path else "text",
                })
        return files

    # ── Manifest persistence ──────────────────────────────────────

    def save_manifest(
        self,
        project_id: str,
        manifest: dict[str, Any],
    ) -> Path:
        """Save a project manifest describing its generated artifacts."""
        path = MANIFESTS_DIR / f"{project_id}.json"
        path.write_text(json.dumps(manifest, indent=2, default=str))
        logger.info("manifest_saved", project_id=project_id, path=str(path))
        return path

    def load_manifest(self, project_id: str) -> Optional[dict[str, Any]]:
        """Load a project manifest."""
        path = MANIFESTS_DIR / f"{project_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    # ── Execution logs ────────────────────────────────────────────

    def save_execution_log(
        self,
        project_id: str,
        log_entry: dict[str, Any],
    ) -> Path:
        """Persist an execution log entry for a pipeline step.

        Logs are stored as newline-delimited JSON (NDJSON) per project:
        ``logs/{project_id}.ndjson``
        """
        path = LOGS_DIR / f"{project_id}.ndjson"
        with path.open("a") as f:
            f.write(json.dumps(log_entry, default=str) + "\n")
        return path

    def load_execution_logs(self, project_id: str) -> list[dict[str, Any]]:
        """Load all execution log entries for a project."""
        path = LOGS_DIR / f"{project_id}.ndjson"
        if not path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    # ── Export ────────────────────────────────────────────────────

    def export_project_zip(
        self,
        project_id: str,
        state: dict[str, Any],
    ) -> Path:
        """Export a complete project (all artifacts) as a ZIP file."""
        export_name = f"project_{project_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        export_dir = STORAGE_DIR / "exports"
        export_dir.mkdir(exist_ok=True)
        zip_path = export_dir / f"{export_name}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for artifact_key in ("requirements", "architecture", "source_code", "test_suite", "documentation"):
                data = state.get(artifact_key)
                if data:
                    zf.writestr(f"{artifact_key}.json", json.dumps(data, indent=2, default=str))

            code = state.get("source_code", {})
            files = code.get("files", []) if isinstance(code, dict) else []
            for entry in files:
                path = entry.get("path", "unknown")
                content = entry.get("content", "")
                zf.writestr(f"generated/{path}", content)

        logger.info("project_exported", project_id=project_id, path=str(zip_path))
        return zip_path

    # ── Cleanup ──────────────────────────────────────────────────

    def clean_old_checkpoints(
        self,
        keep_last: int = 10,
        project_id: Optional[str] = None,
    ) -> int:
        """Remove old checkpoints, keeping only the most recent ``keep_last``."""
        checkpoints = self.list_checkpoints(project_id)
        if len(checkpoints) <= keep_last:
            return 0

        removed = 0
        for cp in checkpoints[keep_last:]:
            cp.unlink()
            removed += 1

        logger.info("old_checkpoints_cleaned", removed=removed, keep_last=keep_last)
        return removed


storage_service = StorageService()
