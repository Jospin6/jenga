import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from pydantic import Field

from backend import main, projects
from backend.agent import graph
from backend.agent.memory import (
    COMPLETION_MESSAGE, CONVERSATION_CHAR_LIMIT, RECENT_MESSAGE_LIMIT,
    conversation_context,
)
from backend.agent.state import File, ImplementationTask, Plan, TaskPlan
from backend.agent.workspace import project_workspace


class ConversationModel(FakeMessagesListChatModel):
    seen_prompts: list[str] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        def respond(prompt):
            self.seen_prompts.append(prompt)
            if schema is Plan:
                return Plan(
                    name="Cafe Memory", description="A cafe website", techstack="HTML",
                    features=["Home"], files=[File(path="index.html", purpose="Home")],
                )
            return TaskPlan(implementation_steps=[
                ImplementationTask(filepath="index.html", task_description="Apply the latest request"),
            ])
        return RunnableLambda(respond)


def model_writing(content):
    return ConversationModel(responses=[
        AIMessage(content="", tool_calls=[{
            "name": "write_file", "args": {"path": "index.html", "content": content},
            "id": str(uuid4()), "type": "tool_call",
        }]),
        AIMessage(content="Done"),
    ])


class ConversationMemoryTests(unittest.TestCase):
    def setUp(self):
        artifacts = Path(__file__).resolve().parents[2] / ".test-artifacts"
        artifacts.mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.agent = graph.compile_agent()
        for patcher in (
            patch.object(projects, "PROJECTS_ROOT", self.root),
            patch.object(main, "get_agent", side_effect=lambda: self.agent),
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(main.app)

    def generate(self, prompt, html, project_id=None):
        model = model_writing(html)
        with patch.object(graph, "get_llm", return_value=model):
            response = self.client.post("/api/generate", json={
                "prompt": prompt, "project_id": project_id,
            })
        self.assertEqual(response.status_code, 200)
        events = [json.loads(frame[6:]) for frame in response.text.strip().split("\n\n")
                  if frame.startswith("data: ")]
        self.assertEqual(events[-1]["type"], "done", events)
        return events[0]["project_id"], model

    def snapshot(self, project_id):
        return self.agent.get_state({"configurable": {"thread_id": project_id}}).values

    def test_edit_keeps_conversation_and_current_code_and_runs_coder_again(self):
        initial = "Create a blue cafe called Cafe Memory"
        before = "<h1>Cafe Memory</h1><p>Keep this description</p>"
        project_id, _ = self.generate(initial, before)
        extra = projects.project_dir(project_id) / "files" / "unrelated.js"
        extra.write_text("const keepMe = true;", encoding="utf-8")
        request = "Add opening hours without removing the description"
        after = before + "<p>Open 9-18</p>"
        _, model = self.generate(request, after, project_id)

        self.assertEqual(len(model.seen_prompts), 2)
        for prompt in model.seen_prompts:  # Both planner and architect receive memory.
            for expected in (initial, request, COMPLETION_MESSAGE, before, "PREVIOUS PROJECT PLAN"):
                self.assertIn(expected, prompt)
        self.assertEqual(projects.read_files(project_id)["index.html"], after)
        self.assertEqual(extra.read_text(), "const keepMe = true;")
        state = self.snapshot(project_id)
        self.assertEqual([message.type for message in state["messages"]], ["human", "ai", "human", "ai"])
        self.assertEqual(len({message.id for message in state["messages"]}), 4)
        self.assertEqual(state["status"], "DONE")
        self.assertEqual(len(projects.load_project(project_id)["history"]), 4)

    def test_projects_keep_separate_conversations_and_files(self):
        first_id, _ = self.generate("Create secret-blue-cafe", "<h1>secret-blue-cafe</h1>")
        second_id, model = self.generate("Create red-portfolio", "<h1>red-portfolio</h1>")
        self.assertNotEqual(first_id, second_id)
        for prompt in model.seen_prompts:
            self.assertNotIn("secret-blue-cafe", prompt)
        self.assertEqual(self.snapshot(first_id)["messages"][0].content, "Create secret-blue-cafe")
        self.assertEqual(self.snapshot(second_id)["messages"][0].content, "Create red-portfolio")

    def test_saved_history_restores_context_after_checkpointer_restart(self):
        project_id, _ = self.generate("Create a green garden website", "<h1>Green garden</h1>")
        self.agent = graph.compile_agent()  # Simulate an empty checkpoint store after restart.
        self.assertFalse(self.snapshot(project_id))
        _, model = self.generate("Add a contact section", "<h1>Green garden</h1><p>Contact</p>", project_id)
        for prompt in model.seen_prompts:
            self.assertIn("Create a green garden website", prompt)
            self.assertIn("<h1>Green garden</h1>", prompt)
        self.assertEqual(len(self.snapshot(project_id)["messages"]), 4)

    def test_direct_graph_calls_remember_prior_turn_without_replaying_history(self):
        async def run():
            config = {"configurable": {"thread_id": "direct-thread"}, "recursion_limit": 100}
            with project_workspace(self.root / "direct"):
                with patch.object(graph, "get_llm", return_value=model_writing("<h1>Initial</h1>")):
                    await self.agent.ainvoke({"user_prompt": "Create a purple shop", "browser_preview": True}, config)
                model = model_writing("<h1>Initial</h1><footer>Contact</footer>")
                with patch.object(graph, "get_llm", return_value=model):
                    await self.agent.ainvoke({"user_prompt": "Add a footer", "browser_preview": True}, config)
                return model

        model = asyncio.run(run())
        for prompt in model.seen_prompts:
            self.assertIn("Create a purple shop", prompt)
            self.assertIn("Add a footer", prompt)
            self.assertIn("<h1>Initial</h1>", prompt)
        self.assertEqual(len(self.snapshot("direct-thread")["messages"]), 4)

    def test_long_conversation_is_bounded_and_keeps_initial_and_latest_requests(self):
        project_id = str(uuid4())
        history = [{"role": "user", "content": "Original brief: a purple shop"}]
        for index in range(20):
            history.extend([
                {"role": "assistant", "content": f"Completed turn {index}"},
                {"role": "user", "content": f"Earlier request {index}: " + "x" * 10_000},
            ])
        projects.save_project({"id": project_id, "name": "Long chat", "history": history})
        _, model = self.generate("Latest request: add contact details", "<h1>Contact</h1>", project_id)
        state = self.snapshot(project_id)
        self.assertLessEqual(len(state["messages"]), RECENT_MESSAGE_LIMIT + 1)
        self.assertEqual(state["messages"][0].content, history[0]["content"])
        self.assertEqual(state["messages"][-2].content, "Latest request: add contact details")
        self.assertLessEqual(len(conversation_context(state["messages"])), CONVERSATION_CHAR_LIMIT)
        for prompt in model.seen_prompts:
            self.assertIn(history[0]["content"], prompt)
            self.assertIn("Latest request: add contact details", prompt)
            self.assertNotIn("Earlier request 0:", prompt)
        self.assertEqual(len(projects.load_project(project_id)["history"]), len(history) + 2)


if __name__ == "__main__":
    unittest.main()
