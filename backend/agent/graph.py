import asyncio
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from .prompts import architect_prompt, coder_system_prompt, planner_prompt
from .state import AgentState, CoderState, Plan, TaskPlan
from .tools import (
    get_current_directory, list_files, read_file, safe_path_for_project,
    safe_read_file, write_file,
)
from .workspace import emit

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BROWSER_CONTRACT = """
RUNTIME CONSTRAINTS (mandatory for this browser preview):
Build a complete, responsive, polished static website using HTML, CSS and vanilla
JavaScript. The entry point MUST be index.html at the project root. Create it FIRST
so the user can see the site while the other files are being generated. Reference
separate CSS files and classic deferred JavaScript files with relative paths.
No npm, framework, JSX, TypeScript, server, ES module imports, CSS @import, fetch,
service workers, localStorage or cookies: the preview runs in an isolated iframe.
Use in-memory state for interactions. Use inline SVG or HTTPS image URLs if useful.
Keep navigation on one page using section anchors. Never simulate a working payment,
authentication, or server API: make the limits explicit in the generated interface.
Use the language of the user's request. Usually 3 to 6 files are enough; maximum 24.
For edits, inspect and preserve existing files and features, changing only what the
user requests. Include all files that are still needed in the updated plan.
"""


@lru_cache(maxsize=1)
def get_llm():
    # Lazy initialization lets /health work before a key is configured.
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"), temperature=0.3,
        streaming=True, timeout=120, max_retries=1,
    )


async def planner_agent(state: AgentState) -> dict:
    emit({"type": "stage", "stage": "planning", "message": "Je prépare le plan de votre site."})
    prompt = planner_prompt(state["user_prompt"])
    if state.get("browser_preview"):
        prompt += BROWSER_CONTRACT
    response = await get_llm().with_structured_output(Plan, method="json_schema").ainvoke(prompt)
    if not response or not 1 <= len(response.files) <= 24:
        raise ValueError("The planner must return between 1 and 24 files.")
    paths = [safe_path_for_project(file.path) for file in response.files]
    if len(paths) != len(set(paths)):
        raise ValueError("The plan contains duplicate paths.")
    if state.get("browser_preview") and safe_path_for_project("index.html") not in paths:
        raise ValueError("The preview requires index.html.")
    emit({"type": "plan", "plan": response.model_dump()})
    return {"plan": response}


async def architect_agent(state: AgentState) -> dict:
    emit({"type": "stage", "stage": "architecture", "message": "J’organise les pages et les fichiers."})
    prompt = architect_prompt(state["plan"])
    if state.get("browser_preview"):
        prompt += BROWSER_CONTRACT
    response = await get_llm().with_structured_output(TaskPlan, method="json_schema").ainvoke(prompt)
    if not response or not response.implementation_steps:
        raise ValueError("The architect returned no implementation steps.")
    planned = {safe_path_for_project(file.path) for file in state["plan"].files}
    steps = response.implementation_steps
    targets = [safe_path_for_project(step.filepath) for step in steps]
    if set(targets) != planned or len(targets) != len(planned):
        raise ValueError("The architecture must implement each planned file exactly once.")
    if state.get("browser_preview"):
        steps.sort(key=lambda step: safe_path_for_project(step.filepath) != safe_path_for_project("index.html"))
    emit({"type": "tasks", "tasks": response.model_dump()["implementation_steps"]})
    return {"task_plan": response}


async def coder_agent(state: AgentState) -> dict:
    coder_state = state.get("coder_state") or CoderState(task_plan=state["task_plan"])
    steps = coder_state.task_plan.implementation_steps
    if coder_state.current_step_idx >= len(steps):
        return {"coder_state": coder_state, "status": "DONE"}

    current_task = steps[coder_state.current_step_idx]
    emit({
        "type": "stage", "stage": "coding", "path": current_task.filepath,
        "step": coder_state.current_step_idx + 1, "total": len(steps),
        "message": f"Création de {current_task.filepath}",
    })
    user_prompt = f"""
        USER REQUEST AND PROJECT CONTEXT:
        {state['user_prompt']}

        GLOBAL PROJECT PLAN:
        {state['plan'].model_dump_json(indent=2)}

        ALL IMPLEMENTATION STEPS:
        {coder_state.task_plan.model_dump_json(indent=2)}

        CURRENT TARGET FILE: {current_task.filepath}
        CURRENT TASK: {current_task.task_description}
        EXISTING TARGET FILE CONTENT:
        {safe_read_file(current_task.filepath) or '[The file does not exist yet]'}

        Inspect related existing files with read_file and list_files. Implement this task
        as part of the complete application. Use exactly the planned interfaces and paths.
        Write complete file contents using write_file. Do not only describe the changes.
    """
    system_prompt = coder_system_prompt()
    if state.get("browser_preview"):
        system_prompt += BROWSER_CONTRACT
    react_agent = create_agent(
        model=get_llm(), tools=[write_file, read_file, list_files, get_current_directory],
        system_prompt=system_prompt,
    )
    await react_agent.ainvoke(
        {"messages": [{"role": "user", "content": user_prompt}]},
        {"recursion_limit": 40},
    )
    if not safe_read_file(current_task.filepath).strip():
        raise ValueError(f"The coder did not write {current_task.filepath}.")
    coder_state = coder_state.model_copy(update={"current_step_idx": coder_state.current_step_idx + 1})
    emit({"type": "task_done", "path": current_task.filepath, "step": coder_state.current_step_idx, "total": len(steps)})
    return {"coder_state": coder_state, "status": "DONE" if coder_state.current_step_idx >= len(steps) else "CODING"}


graph = StateGraph(AgentState)
graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_node("coder", coder_agent)
graph.add_edge("planner", "architect")
graph.add_edge("architect", "coder")
graph.add_conditional_edges("coder", lambda state: END if state.get("status") == "DONE" else "coder")
graph.set_entry_point("planner")
agent = graph.compile()

if __name__ == "__main__":
    result = asyncio.run(agent.ainvoke(
        {"user_prompt": "Create a simple working calculator website", "browser_preview": True},
        {"recursion_limit": 100},
    ))
    print(result)
