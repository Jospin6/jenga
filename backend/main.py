import asyncio
import io
import logging
import os
import zipfile
from contextlib import suppress
from pathlib import Path
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

if __package__:
    from .projects import load_project, project_dir, read_files, save_project
    from .agent.workspace import project_workspace
    from .streaming import FileDrafts, sse
else:
    # Vercel loads main.py directly when its Root Directory is backend/.
    from projects import load_project, project_dir, read_files, save_project
    from agent.workspace import project_workspace
    from streaming import FileDrafts, sse

load_dotenv(Path(__file__).resolve().parent / ".env")
app = FastAPI(title="Jenga — Website builder", version="1.0.0")
logger = logging.getLogger(__name__)
active_projects: set[str] = set()


def get_agent():
    if __package__:
        from .agent.graph import agent
    else:
        from agent.graph import agent
    return agent


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=12000)
    project_id: UUID | None = None

    @field_validator("prompt")
    @classmethod
    def clean_prompt(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Décrivez votre site en au moins 3 caractères.")
        return value


def find_project(project_id: UUID) -> dict:
    try:
        return load_project(str(project_id))
    except FileNotFoundError:
        raise HTTPException(404, "Projet introuvable.") from None


@app.get("/api/health")
async def health():
    return {"status": "ok", "configured": bool(os.getenv("OPENAI_API_KEY"))}


@app.get("/api/projects/{project_id}")
async def project(project_id: UUID):
    data = find_project(project_id)
    if data.get("status") == "generating" and str(project_id) not in active_projects:
        data["status"] = "cancelled"
    return {**data, "files": read_files(str(project_id))}


@app.get("/api/projects/{project_id}/download")
async def download(project_id: UUID):
    find_project(project_id)
    files = read_files(str(project_id))
    if not files:
        raise HTTPException(404, "Aucun fichier à télécharger.")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path, content in files.items():
            bundle.writestr(path, content)
    return Response(archive.getvalue(), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="jenga-{project_id}.zip"',
        "Cache-Control": "no-store",
    })


@app.post("/api/generate")
async def generate(body: GenerateRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(503, "Ajoutez OPENAI_API_KEY dans backend/.env puis redémarrez le backend.")
    if body.project_id:
        data = find_project(body.project_id)
    else:
        data = {"id": str(uuid4()), "name": "Nouveau projet", "history": []}
    project_id = data["id"]
    if project_id in active_projects:
        raise HTTPException(409, "Une génération est déjà en cours pour ce projet.")
    active_projects.add(project_id)
    data["status"] = "generating"
    data["history"].append({"role": "user", "content": body.prompt})
    try:
        save_project(data)
    except Exception:
        active_projects.discard(project_id)
        raise

    async def events():
        queue: asyncio.Queue = asyncio.Queue(maxsize=128)

        async def run():
            try:
                async with asyncio.timeout(900):
                    with project_workspace(project_dir(project_id) / "files"):
                        existing = read_files(project_id)
                        context = "\n".join(item["content"] for item in data["history"][-8:])
                        if existing:
                            context += "\nExisting project files (inspect them before edits):\n" + "\n".join(existing)
                        drafts = FileDrafts()
                        async for part in get_agent().astream(
                            {"user_prompt": context, "browser_preview": True},
                            {"recursion_limit": 100}, stream_mode=["custom", "messages"],
                            subgraphs=True, version="v2",
                        ):
                            if part["type"] == "custom":
                                event = part["data"]
                                if event.get("type") == "plan":
                                    data["name"] = event["plan"]["name"]
                                    data["plan"] = event["plan"]
                                await queue.put(event)
                            elif part["type"] == "messages":
                                message, _metadata = part["data"]
                                for event in drafts.consume(message, part["ns"]):
                                    await queue.put(event)
                        files = read_files(project_id)
                        if not files.get("index.html", "").strip():
                            raise ValueError("No preview entry point was generated.")
                        data["status"] = "completed"
                        data["history"].append({"role": "assistant", "content": "Votre site est prêt. Vous pouvez le prévisualiser ou demander des modifications."})
                        await queue.put({"type": "done", "project_id": project_id, "files": files})
            except asyncio.CancelledError:
                data["status"] = "cancelled"
                raise
            except Exception as error:
                logger.exception("Generation failed for project %s", project_id)
                data["status"] = "error"
                message = {
                    "AuthenticationError": "La clé API du modèle est invalide. Vérifiez backend/.env.",
                    "RateLimitError": "Le quota du modèle est atteint. Vérifiez votre crédit ou réessayez plus tard.",
                    "APITimeoutError": "Le modèle met trop de temps à répondre. Réessayez.",
                    "TimeoutError": "La génération a dépassé 15 minutes. Les fichiers sauvegardés sont conservés.",
                }.get(type(error).__name__, "La génération a échoué. Les fichiers sauvegardés sont conservés. Consultez les logs du backend puis réessayez.")
                await queue.put({"type": "error", "message": message})
            finally:
                try:
                    save_project(data)
                finally:
                    active_projects.discard(project_id)

        task = asyncio.create_task(run())
        try:
            yield sse({"type": "start", "project_id": project_id})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    if task.done():
                        task.result()
                        break
                    yield ": keepalive\n\n"
                    continue
                yield sse(event)
                if event["type"] in {"done", "error"}:
                    await task
                    break
        finally:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
    })


@app.get("/")
def root():
    return {"message": "Welcom to jenga api"}
