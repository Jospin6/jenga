"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { readEventStream, responseError } from "./stream";
import type { Files, Message, Plan, Project, RecentProject, Status, StreamEvent, Task } from "./types";

type State = {
  id: string | null; name: string; status: Status; messages: Message[];
  files: Files; savedFiles: Files; plan: Plan | null; tasks: Task[]; completed: string[];
  stage: string; activity: string; activeFile: string; error: string | null; recent: RecentProject[];
};
const initial: State = {
  id: null, name: "Nouveau projet", status: "idle", messages: [], files: {}, savedFiles: {},
  plan: null, tasks: [], completed: [], stage: "", activity: "", activeFile: "", error: null, recent: [],
};
type Action =
  | { type: "event"; event: StreamEvent }
  | { type: "begin"; prompt: string }
  | { type: "failure"; message: string; cancelled?: boolean }
  | { type: "load"; project: Project }
  | { type: "loading" }
  | { type: "reset" }
  | { type: "recent"; projects: RecentProject[] };

function reducer(state: State, action: Action): State {
  if (action.type === "reset") return { ...initial, recent: state.recent };
  if (action.type === "recent") return { ...state, recent: action.projects };
  if (action.type === "loading") return { ...state, status: "loading", error: null };
  if (action.type === "load") {
    const project = action.project;
    return {
      ...initial, recent: state.recent, id: project.id, name: project.name, status: project.status === "generating" ? "cancelled" : project.status,
      messages: project.history, files: project.files, savedFiles: project.files, plan: project.plan || null
    };
  }
  if (action.type === "begin") return {
    ...state, status: "generating", error: null, completed: [], tasks: [], stage: "planning", activeFile: "",
    activity: "Connexion à votre agent…", messages: [...state.messages, { role: "user", content: action.prompt }],
  };
  if (action.type === "failure") return {
    ...state, status: action.cancelled ? "cancelled" : "error", files: state.savedFiles,
    error: action.cancelled ? null : action.message, activity: action.cancelled ? "Génération arrêtée. Vos fichiers sauvegardés sont conservés." : action.message
  };

  const event = action.event;
  switch (event.type) {
    case "start": return { ...state, id: event.project_id };
    case "stage": return { ...state, stage: event.stage, activity: event.message, activeFile: event.path || state.activeFile };
    case "plan": return { ...state, plan: event.plan, name: event.plan.name };
    case "tasks": return { ...state, tasks: event.tasks };
    case "file_delta": return { ...state, files: { ...state.files, [event.path]: event.content }, activeFile: event.path };
    case "file": return { ...state, files: { ...state.files, [event.path]: event.content }, savedFiles: { ...state.savedFiles, [event.path]: event.content } };
    case "task_done": return { ...state, completed: [...new Set([...state.completed, event.path])] };
    case "done": return {
      ...state, status: "completed", files: event.files, savedFiles: event.files, activeFile: "", activity: "Votre site est prêt.",
      messages: [...state.messages, { role: "assistant", content: "Votre site est prêt. Explorez l’aperçu ou dites-moi ce que vous souhaitez modifier." }]
    };
    case "error": return { ...state, status: "error", files: state.savedFiles, error: event.message };
    default: return state;
  }
}

// Keep the legacy key so existing projects remain available after the Jenga rename.
const STORAGE_KEY = "atelier.projects.v1";

export function useBuilder() {
  const [state, dispatch] = useReducer(reducer, initial);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (Array.isArray(parsed)) dispatch({ type: "recent", projects: parsed.filter((p) => p && typeof p.id === "string" && typeof p.name === "string").slice(0, 12) });
    } catch { /* Local storage is optional. */ }
    return () => controller.current?.abort();
  }, []);

  useEffect(() => {
    if (!state.id || state.status === "loading") return;
    let projects: RecentProject[] = [];
    try { projects = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch { /* Optional persistence. */ }
    if (!Array.isArray(projects)) projects = [];
    const next = [{ id: state.id, name: state.name, updatedAt: new Date().toISOString() }, ...projects.filter((p) => p && p.id !== state.id)].slice(0, 12);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* Storage can be full or disabled. */ }
    dispatch({ type: "recent", projects: next });
  }, [state.id, state.name, state.status]);

  const generate = useCallback(async (prompt: string) => {
    if (controller.current || prompt.trim().length < 3) return;
    const abort = new AbortController();
    controller.current = abort;
    dispatch({ type: "begin", prompt: prompt.trim() });
    try {
      const response = await fetch("/api/generate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt.trim(), project_id: state.id }), signal: abort.signal,
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!response.body) throw new Error("Le navigateur ne prend pas en charge le streaming.");
      let terminal = false;
      for await (const event of readEventStream(response.body)) {
        dispatch({ type: "event", event });
        if (event.type === "done" || event.type === "error") { terminal = true; break; }
      }
      if (!terminal) throw new Error("La connexion a été interrompue. Vous pouvez relancer la génération.");
    } catch (error) {
      dispatch({ type: "failure", cancelled: abort.signal.aborted, message: error instanceof Error ? error.message : "La génération a échoué." });
    } finally {
      controller.current = null;
    }
  }, [state.id]);

  const openProject = useCallback(async (id: string) => {
    if (controller.current) return;
    const abort = new AbortController();
    controller.current = abort;
    dispatch({ type: "loading" });
    try {
      const response = await fetch(`/api/projects/${id}`, { signal: abort.signal });
      if (!response.ok) throw new Error(await responseError(response));
      dispatch({ type: "load", project: await response.json() });
    } catch (error) {
      dispatch({ type: "failure", message: error instanceof Error ? error.message : "Impossible d’ouvrir le projet." });
    } finally { controller.current = null; }
  }, []);

  return {
    state, generate, openProject, stop: () => controller.current?.abort(),
    newProject: () => { if (!controller.current) dispatch({ type: "reset" }); }
  };
}
