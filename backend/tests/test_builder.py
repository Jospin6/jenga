import asyncio
import errno
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

# Tests use a fake model and never export traces or call a paid provider.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.runnables import RunnableLambda

from backend import main, projects
from backend.agent.state import File, ImplementationTask, Plan, TaskPlan
from backend.agent.tools import safe_path_for_project, write_file
from backend.agent.workspace import project_root, project_workspace
from backend.streaming import FileDrafts

PLAN = Plan(name="Test café", description="Un café", techstack="HTML/CSS/JS", features=["Accueil"], files=[File(path="index.html", purpose="Accueil")])
TASKS = TaskPlan(implementation_steps=[ImplementationTask(filepath="index.html", task_description="Créer la page")])


class ToolModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        return RunnableLambda(lambda _: PLAN if schema is Plan else TASKS)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        artifacts = Path(__file__).resolve().parents[2] / ".test-artifacts"
        artifacts.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.root_patch = patch.object(projects, "PROJECTS_ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.client = TestClient(main.app)

    def test_missing_key_and_invalid_requests(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertFalse(self.client.get("/api/health").json()["configured"])
            self.assertEqual(self.client.post("/api/generate", json={"prompt": "Un café"}).status_code, 503)
        self.assertEqual(self.client.post("/api/generate", json={"prompt": "   "}).status_code, 422)
        self.assertEqual(self.client.post("/api/generate", json={"prompt": "x" * 12001}).status_code, 422)
        self.assertEqual(self.client.get("/api/projects/not-a-uuid").status_code, 422)
        self.assertEqual(self.client.get(f"/api/projects/{uuid4()}").status_code, 404)

    def test_real_graph_streams_nested_tool_writes_and_saves_project(self):
        from backend.agent import graph

        model = ToolModel(responses=[
            AIMessage(content="", tool_calls=[{"name": "write_file", "args": {"path": "index.html", "content": "<h1>Bonjour café</h1>"}, "id": "write-1", "type": "tool_call"}]),
            AIMessage(content="Terminé"),
        ])
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.object(graph, "get_llm", return_value=model):
            response = self.client.post("/api/generate", json={"prompt": "Un site de café"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers["content-type"])
            events = [json.loads(frame[6:]) for frame in response.text.strip().split("\n\n") if frame.startswith("data: ")]
            kinds = [event["type"] for event in events]
            self.assertEqual(kinds[0], "start")
            for kind in ("stage", "plan", "tasks", "file", "task_done", "done"):
                self.assertIn(kind, kinds)
            self.assertEqual(kinds[-1], "done")
            self.assertLess(kinds.index("file"), kinds.index("done"))
            project_id = events[0]["project_id"]
            saved = self.client.get(f"/api/projects/{project_id}").json()
            self.assertEqual(saved["status"], "completed")
            self.assertEqual(saved["files"]["index.html"], "<h1>Bonjour café</h1>")
            self.assertEqual(saved["name"], "Test café")
            archive = self.client.get(f"/api/projects/{project_id}/download")
            with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
                self.assertEqual(bundle.namelist(), ["index.html"])
                self.assertIn("café", bundle.read("index.html").decode())
            edit = self.client.post("/api/generate", json={"prompt": "Ajoute une section", "project_id": project_id})
            self.assertIn('"type": "done"', edit.text)
            self.assertEqual(len(projects.load_project(project_id)["history"]), 4)
            self.assertNotIn(project_id, main.active_projects)

    def test_concurrent_workspaces_do_not_mix_and_paths_cannot_escape(self):
        async def write(name):
            with project_workspace(self.root / name):
                await asyncio.sleep(0)
                await write_file.ainvoke({"path": "index.html", "content": name})
                for path in ("../secret", str(self.root / "secret")):
                    with self.assertRaises(ValueError):
                        safe_path_for_project(path)
                return project_root()

        async def run():
            return await asyncio.gather(write("one"), write("two"))

        roots = asyncio.run(run())
        self.assertNotEqual(*roots)
        for name in ("one", "two"):
            self.assertEqual((self.root / name / "index.html").read_text(), name)

    def test_partial_tool_json_preserves_unicode_and_newlines(self):
        with project_workspace(self.root / "draft"):
            drafts = FileDrafts()
            first = AIMessageChunk(content="", id="message-1", tool_call_chunks=[{"name": "write_file", "args": '{"path":"index.html","content":"<h1>Café', "id": "call-1", "index": 0}])
            self.assertEqual(list(drafts.consume(first))[0]["content"], "<h1>Café")
            for call in drafts.calls.values():
                call["time"] = 0
            second = AIMessageChunk(content="", id="message-1", tool_call_chunks=[{"name": None, "args": '</h1>\\n🙂"}', "id": None, "index": 0}])
            self.assertEqual(list(drafts.consume(second))[0]["content"], "<h1>Café</h1>\n🙂")

    def test_provider_errors_are_terminal_and_do_not_leak_details(self):
        class FailingGraph:
            async def astream(self, *args, **kwargs):
                raise RuntimeError("private-provider-token")
                yield

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch.object(main, "get_agent", return_value=FailingGraph()), self.assertLogs("backend.main", level="ERROR"):
            response = self.client.post("/api/generate", json={"prompt": "Un site"})
        self.assertIn('"type": "error"', response.text)
        self.assertNotIn("private-provider-token", response.text)
        self.assertNotIn('"type": "done"', response.text)
        self.assertFalse(main.active_projects)

    def test_unwritable_storage_returns_clear_error_before_calling_model(self):
        error = OSError(errno.EROFS, "Read-only file system", "/private/deployment/path")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), \
                patch.object(main, "save_project", side_effect=error), \
                patch.object(main, "get_agent") as get_agent, \
                self.assertLogs("backend.main", level="ERROR"):
            response = self.client.post("/api/generate", json={"prompt": "Un site"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("stockage", response.json()["detail"])
        self.assertNotIn("/private/deployment/path", response.text)
        self.assertFalse(main.active_projects)
        get_agent.assert_not_called()

    def test_disconnect_cancels_agent_and_releases_project(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()

        class SlowGraph:
            async def astream(self, *args, **kwargs):
                started.set()
                try:
                    await asyncio.sleep(60)
                finally:
                    cancelled.set()
                yield

        async def run():
            response = await main.generate(main.GenerateRequest(prompt="Un site lent"))
            iterator = response.body_iterator
            first = json.loads((await anext(iterator)).removeprefix("data: "))
            await asyncio.wait_for(started.wait(), timeout=2)
            await iterator.aclose()
            self.assertTrue(cancelled.is_set())
            self.assertEqual(projects.load_project(first["project_id"])["status"], "cancelled")
            self.assertNotIn(first["project_id"], main.active_projects)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch.object(main, "get_agent", return_value=SlowGraph()):
            asyncio.run(run())

    def test_same_project_cannot_generate_twice(self):
        project_id = str(uuid4())
        projects.save_project({"id": project_id, "history": [], "name": "Busy"})
        main.active_projects.add(project_id)
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
                response = self.client.post("/api/generate", json={"prompt": "Un site", "project_id": project_id})
            self.assertEqual(response.status_code, 409)
        finally:
            main.active_projects.discard(project_id)


if __name__ == "__main__":
    unittest.main()
