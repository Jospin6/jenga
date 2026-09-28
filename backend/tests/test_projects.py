import errno
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


class ProjectStorageTests(unittest.TestCase):
    def setUp(self):
        self.backend = Path(__file__).resolve().parents[1]
        artifacts = self.backend.parent / ".test-artifacts"
        artifacts.mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()

    def load_store(self, *, vercel="", projects_dir=""):
        spec = importlib.util.spec_from_file_location("test_project_store", self.backend / "projects.py")
        store = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"VERCEL": vercel, "PROJECTS_DIR": projects_dir}), \
                patch("tempfile.gettempdir", return_value=str(self.root / "tmp")):
            spec.loader.exec_module(store)
        return store

    def test_local_default_preserves_existing_projects_location(self):
        store = self.load_store()
        self.assertEqual(store.PROJECTS_ROOT, self.backend.parent / "generated_projects")

    def test_vercel_saves_with_only_temporary_directory_writable(self):
        store = self.load_store(vercel="1")
        scratch = self.root / "tmp"
        scratch.mkdir()
        mkdir = Path.mkdir

        def restricted_mkdir(path, *args, **kwargs):
            if not path.resolve().is_relative_to(scratch):
                raise OSError(errno.EROFS, "Read-only file system", str(path))
            return mkdir(path, *args, **kwargs)

        project = {"id": str(uuid4()), "name": "Café", "history": []}
        with patch.object(Path, "mkdir", restricted_mkdir):
            store.save_project(project)
            files = store.project_dir(project["id"]) / "files"
            files.mkdir()
            (files / "index.html").write_text("<h1>Café</h1>", encoding="utf-8")

        self.assertTrue(store.project_dir(project["id"]).is_relative_to(scratch))
        self.assertEqual(store.load_project(project["id"])["name"], "Café")
        self.assertEqual(store.read_files(project["id"]), {"index.html": "<h1>Café</h1>"})

    def test_environment_can_select_storage_directory(self):
        custom = self.root / "custom-projects"
        store = self.load_store(vercel="1", projects_dir=str(custom))
        project = {"id": str(uuid4()), "name": "Custom", "history": []}
        store.save_project(project)
        self.assertTrue((custom / project["id"] / "project.json").is_file())
        self.assertEqual(store.load_project(project["id"])["name"], "Custom")


if __name__ == "__main__":
    unittest.main()
