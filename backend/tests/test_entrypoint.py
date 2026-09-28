"""Exercise the backend-only deployment without the repository on sys.path."""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class EntrypointTests(unittest.TestCase):
    def test_vercel_loads_backend_without_parent_package(self):
        backend = Path(__file__).resolve().parents[1]
        artifacts = backend.parent / ".test-artifacts"
        artifacts.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts) as directory:
            deployment = Path(directory)
            for filename in ("main.py", "projects.py", "streaming.py"):
                shutil.copy2(backend / filename, deployment / filename)
            shutil.copytree(
                backend / "agent", deployment / "agent",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            script = textwrap.dedent('''
                import importlib.util
                import sys
                from pathlib import Path

                deployment = Path(sys.argv[1])
                sys.path.insert(0, str(deployment))
                assert importlib.util.find_spec("backend") is None

                # Load by file path as the Vercel runtime does.
                spec = importlib.util.spec_from_file_location("main", deployment / "main.py")
                main = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(main)

                from fastapi.testclient import TestClient
                with TestClient(main.app) as client:
                    response = client.get("/api/health")
                    assert response.status_code == 200, response.text
                    assert response.json() == {"status": "ok", "configured": False}
                    assert client.get("/docs").status_code == 200

                # Also load the lazy graph and verify shared file context.
                assert callable(main.get_agent().astream)
                from agent.tools import write_file
                from agent.workspace import project_root
                from langchain_core.messages import AIMessageChunk
                with main.project_workspace(deployment / "files"):
                    assert project_root() == (deployment / "files").resolve()
                    write_file.invoke({"path": "index.html", "content": "<h1>Test</h1>"})
                    assert (deployment / "files" / "index.html").read_text() == "<h1>Test</h1>"
                    chunk = AIMessageChunk(content="", id="test", tool_call_chunks=[{
                        "name": "write_file", "args": '{"path":"index.html","content":"<h1>Test</h1>"}',
                        "id": "write-1", "index": 0,
                    }])
                    assert list(main.FileDrafts().consume(chunk)) == [{
                        "type": "file_delta", "path": "index.html", "content": "<h1>Test</h1>",
                    }]
            ''')
            result = subprocess.run(
                [sys.executable, "-I", "-c", script, str(deployment)],
                cwd=deployment,
                env={**os.environ, "OPENAI_API_KEY": "", "PYTHON_DOTENV_DISABLED": "1",
                     "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"},
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
