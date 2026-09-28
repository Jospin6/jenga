"use client";

import { useEffect, useRef, useState } from "react";
import { useBuilder } from "@/lib/use-builder";
import { responseError } from "@/lib/stream";
import { BrandMark, Icon, type IconName } from "./icons";
import { PromptBox } from "./prompt-box";
import { PreviewPanel } from "./preview-panel";

const inspirations = [
  { name: "Un portfolio qui vous ressemble", category: "Portfolio", theme: "studio", prompt: "Crée un portfolio de designer indépendant en français, avec un style éditorial violet et crème, une section projets, une présentation et un formulaire de contact interactif." },
  { name: "Vos données, en un coup d’œil", category: "Dashboard", theme: "dashboard", prompt: "Crée un tableau de bord analytique en français, clair et moderne, avec des indicateurs de ventes, des graphiques en SVG, un tableau de commandes filtrable et des données de démonstration." },
  { name: "Une belle vitrine pour votre café", category: "Commerce", theme: "cafe", prompt: "Crée un site vitrine chaleureux en français pour un café nommé Maison Moka, avec un design crème et terracotta, un menu filtrable, les horaires, l’adresse et une section à propos." },
];
const suggestions: { label: string; icon: IconName; prompt: string }[] = [
  { label: "Portfolio", icon: "grid", prompt: inspirations[0].prompt },
  { label: "Landing page", icon: "globe", prompt: "Crée une landing page en français pour une application de productivité, avec un design minimaliste, des fonctionnalités, des tarifs et une FAQ interactive." },
  { label: "Dashboard", icon: "code", prompt: inspirations[1].prompt },
  { label: "Site de restaurant", icon: "spark", prompt: inspirations[2].prompt },
];

function InspirationArt({ theme }: { theme: string }) {
  if (theme === "studio") return <div className="template-art studio-art" aria-hidden="true">
    <div className="mini-nav">
      <b>Studio Olivia®</b>
      <span>Projets &nbsp; À propos ↗</span>
    </div>
    <div className="studio-art-content">
      <div>
        <span className="mini-label">DESIGNER INDÉPENDANTE</span>
        <strong>Des idées.<br />Du caractère.</strong>
        <span className="mini-pill">Découvrir mon univers ↗</span>
      </div>
      <div className="abstract-flower">
        <i />
        <i />
        <i />
        <i />
      </div>
    </div>
    <div className="mini-caption">IDENTITÉ VISUELLE &nbsp; · &nbsp; DESIGN DIGITAL</div>
  </div>;
  if (theme === "dashboard") return <div className="template-art dashboard-art" aria-hidden="true">
    <div className="mini-nav">
      <b>
        <span className="mini-logo" />pulse</b>
      <span>Vue d’ensemble &nbsp; ◉</span>
    </div>
    <div className="dashboard-mini-body">
      <div className="mini-sidebar">
        <i />
        <i />
        <i />
        <i />
      </div>
      <div className="mini-analytics">
        <b>Un regard sur votre activité</b>
        <div className="mini-stats">
          <span>Revenus<strong>24 850 €</strong>
            <small>↗ 18,6 %</small>
          </span>
          <span>Clients<strong>1 284</strong>
            <small>↗ 12,4 %</small>
          </span>
          <span>Conversion<strong>4,8 %</strong>
            <small>↗ 2,1 %</small>
          </span>
        </div>
        <div className="mini-chart">{[35, 48, 41, 64, 55, 73, 60, 83, 70, 92, 80, 100].map((height, index) =>
          <i key={index} style={{ height: `${height}%` }} />)}</div>
      </div>
    </div>
  </div>;
  return <div className="template-art cafe-art" aria-hidden="true">
    <div className="mini-nav">
      <b>MAISON MOKA</b>
      <span>Le café &nbsp; La carte &nbsp; ↗</span>
    </div>
    <div className="cafe-art-content">
      <div>
        <span className="mini-label">CAFÉ DE QUARTIER, DEPUIS 2018</span>
        <strong>Les belles journées<br />commencent ici.</strong>
        <span className="mini-pill">Prenez le temps d’un café ↗</span>
      </div>
      <div className="coffee-cup">
        <span />
        <i />
      </div>
    </div>
    <div className="mini-caption">DU BON CAFÉ. DES GENS BIEN. TOUT SIMPLEMENT.</div>
  </div>;
}

export function Builder() {
  const { state, generate, openProject, newProject, stop } = useBuilder();
  const [view, setView] = useState<"home" | "projects">("home");
  const [draft, setDraft] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [health, setHealth] = useState<"checking" | "ready" | "unconfigured" | "offline">("checking");
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const chatEnd = useRef<HTMLDivElement>(null);
  const working = state.status === "generating";
  const busy = working || state.status === "loading";
  const inProject = view === "home" && (state.messages.length > 0 || !!state.id);

  useEffect(() => {
    const abort = new AbortController();
    const check = async () => {
      try {
        const response = await fetch("/api/health", { signal: abort.signal });
        if (!response.ok) { setHealth("offline"); return; }
        const data = await response.json();
        setHealth(data.configured ? "ready" : "unconfigured");
      } catch { if (!abort.signal.aborted) setHealth("offline"); }
    };
    void check();
    const interval = setInterval(check, 30000);
    return () => { abort.abort(); clearInterval(interval); };
  }, []);
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [state.messages.length, state.stage, state.status]);

  function startNew() {
    if (busy) return;
    newProject(); setView("home"); setDraft(""); setSidebarOpen(false); setDownloadError("");
  }
  function selectInspiration(prompt: string) { setDraft(prompt); promptRef.current?.focus(); }
  function open(id: string) { setView("home"); setSidebarOpen(false); setDownloadError(""); void openProject(id); }
  async function download() {
    if (!state.id) return;
    setDownloading(true); setDownloadError("");
    try {
      const response = await fetch(`/api/projects/${state.id}/download`);
      if (!response.ok) throw new Error(await responseError(response));
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url; link.download = `${state.name.replace(/[^\p{L}\p{N}_-]+/gu, "-") || "mon-site"}.zip`;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setDownloadError(error instanceof Error ? error.message : "Le téléchargement a échoué."); }
    finally { setDownloading(false); }
  }

  return <div className={`app-shell ${inProject ? "project-open" : ""}`}>
    {sidebarOpen && <button className="sidebar-backdrop" aria-label="Fermer le menu" onClick={() => setSidebarOpen(false)} />}
    <aside className={`sidebar ${sidebarOpen ? "is-open" : ""}`}>
      <button className="brand" onClick={startNew} disabled={busy} aria-label="Jenga, accueil">
        <BrandMark />
        <span>Jenga<span className="brand-period">.</span>
        </span>
      </button>
      <nav className="main-nav" aria-label="Navigation principale">
        <button className={`nav-button ${view === "home" && !inProject ? "current" : ""}`} onClick={startNew} disabled={busy}>
          <Icon name="plus" />
          <span>Nouveau projet</span>
          <span className="nav-shortcut">＋</span>
        </button>
        <button className={`nav-button ${view === "projects" ? "current" : ""}`} onClick={() => { setView("projects"); setSidebarOpen(false); }} disabled={busy}>
          <Icon name="grid" />
          <span>Mes projets</span>{state.recent.length > 0 && <span className="nav-count">{state.recent.length}</span>}</button>
      </nav>
      <div className="recent-section">
        <span className="sidebar-label">RÉCENTS</span>{state.recent.length ? <div className="recent-list">{state.recent.slice(0, 7).map((project) =>
          <button key={project.id} className={`recent-item ${state.id === project.id && inProject ? "selected" : ""}`} onClick={() => open(project.id)} disabled={busy} title={project.name}>
            <Icon name="folder" size={16} />
            <span>{project.name}</span>
          </button>)}</div> : <div className="recent-empty">
          <Icon name="folder" size={21} />
          <p>Vos prochaines idées<br />trouveront leur place ici.</p>
        </div>}</div>
      <div className="sidebar-bottom">
        <div className="small-note">
          <p>
            <br />
          </p>
        </div>
        <div className="agent-connection" role="status">
          <i className={health} />
          <span>{health === "ready" ? "Agent connecté" : health === "offline" ? "Agent hors ligne" : health === "unconfigured" ? "Clé API à configurer" : "Connexion à l’agent…"}</span>
        </div>
        <div className="profile">
          <div className="profile-avatar">V</div>
          <div>Espace Jenga<span>Espace de création</span>
          </div>
          <Icon name="spark" size={15} />
        </div>
      </div>
    </aside>
    <main className="main-area">
      <header className="topbar">
        <div className="topbar-left">
          <button className="icon-button mobile-menu" aria-label="Ouvrir le menu" onClick={() => setSidebarOpen(true)}>
            <Icon name="menu" />
          </button>
          <span className="breadcrumb">Votre espace</span>
          <span className="breadcrumb-divider">/</span>
          <span className="breadcrumb-current">{inProject ? state.name : view === "projects" ? "Mes projets" : "Nouveau projet"}</span>
        </div>
        <div className="topbar-right">{inProject ? <>
          <span className={`project-status ${state.status}`}>
            <i />{working ? "Création en cours" : state.status === "completed" ? "Prêt à explorer" : state.status === "cancelled" ? "En pause" : state.status === "error" ? "À réessayer" : "Votre projet"}</span>
          <button aria-label="Télécharger le projet" className="download-button" onClick={download} disabled={working || downloading || !Object.keys(state.savedFiles).length}>
            <Icon name={downloading ? "loader" : "download"} size={15} className={downloading ? "spin" : ""} />
            <span>Télécharger</span>
          </button>
        </> : <span className="made-for-ideas">
          <span />Un espace pour vos idées</span>}</div>
      </header>

      {state.status === "loading" ? <div className="loading-project">
        <Icon name="loader" className="spin" size={26} />
        <p>Ouverture de votre projet…</p>
      </div> : inProject ? <div className="builder-workspace">
        <section className="conversation" aria-label="Conversation avec l’agent">
          <div className="conversation-heading">
            <span>
              <BrandMark small />Votre partenaire créatif</span>
            <span className="ai-badge">IA</span>
          </div>
          <div className="conversation-scroll">
            <div className="conversation-intro">
              <span className="eyebrow">ON CRÉE QUOI, AUJOURD’HUI ?</span>
              <p>De votre première idée aux derniers détails, construisons votre site ensemble.</p>
            </div>
            {state.messages.map((message, index) =>
              <div className={`message ${message.role}`} key={index}>{message.role === "assistant" && <BrandMark small />}<div>{message.content}</div>
              </div>)}
            {state.plan && <div className="plan-card">
              <div className="plan-card-title">
                <Icon name="check" size={15} />
                <span>Le plan de votre site</span>
              </div>
              <h3>{state.plan.name}</h3>
              <p>{state.plan.description}</p>
              <ul>{state.plan.features.slice(0, 5).map((feature, index) =>
                <li key={index}>
                  <span />{feature}</li>)}</ul>
            </div>}
            {(working || state.tasks.length > 0) && <div className="generation-progress">
              <div className="progress-title">
                <Icon name={working ? "loader" : state.status === "completed" ? "check" : "stop"} className={working ? "spin" : ""} size={16} />
                <span>{working ? state.activity : state.status === "completed" ? "Création terminée" : "Création interrompue"}</span>
              </div>{state.tasks.length > 0 && <>
                <div className="progress-track">
                  <span style={{ width: `${state.completed.length / state.tasks.length * 100}%` }} />
                </div>
                <div className="task-list">{state.tasks.map((task) =>
                  <div className={`task-row ${state.completed.includes(task.filepath) ? "complete" : ""}`} key={task.filepath}>
                    <Icon name={state.completed.includes(task.filepath) ? "check" : working && task.filepath === state.activeFile ? "loader" : "file"} size={14} className={working && task.filepath === state.activeFile && !state.completed.includes(task.filepath) ? "spin" : ""} />
                    <span>{task.filepath}</span>
                  </div>)}</div>
                <span className="progress-caption">{state.completed.length} sur {state.tasks.length} fichiers terminés</span>
              </>}</div>}
            {state.status === "cancelled" && <p className="notice">Génération arrêtée. Demandez à l’agent de continuer pour reprendre votre projet.</p>}
            {(state.error || downloadError) && <div className="error-notice" role="alert">
              <strong>Un petit contretemps</strong>
              <p>{state.error || downloadError}</p>{state.error && <button className="text-button" onClick={() => { const last = [...state.messages].reverse().find((m) => m.role === "user"); if (last) void generate(last.content); }}>Réessayer <Icon name="refresh" size={13} />
              </button>}</div>}
            <div ref={chatEnd} />
          </div>
          <div className="conversation-composer">
            <PromptBox compact busy={working} onSubmit={(prompt) => void generate(prompt)} onStop={stop} />
            <span className="composer-hint">{working ? "Vous pouvez arrêter la génération à tout moment." : "Entrée pour envoyer · Maj + Entrée pour une nouvelle ligne"}</span>
          </div>
        </section>
        <PreviewPanel key={state.id || "new"} files={state.files} savedFiles={state.savedFiles} status={state.status} activeFile={state.activeFile} name={state.name} />
      </div> : view === "projects" ? <div className="projects-page">
        <div className="section-heading">
          <div>
            <span className="eyebrow">VOTRE COLLECTION</span>
            <h1>De belles idées, devenues projets.</h1>
            <p>Retrouvez vos créations et continuez à leur donner forme.</p>
          </div>
          <button className="primary-button" onClick={startNew}>
            <Icon name="plus" size={17} />Nouveau projet</button>
        </div>{state.recent.length ? <div className="project-grid">{state.recent.map((project, index) =>
          <button className="saved-project" key={project.id} onClick={() => open(project.id)}>
            <div className={`saved-project-art color-${index % 3}`}>
              <Icon name="globe" size={42} />
              <span>{project.name.slice(0, 1).toUpperCase()}</span>
            </div>
            <div>
              <h3>{project.name}</h3>
              <p>Ouvrir le projet <Icon name="chevron" size={14} />
              </p>
            </div>
          </button>)}</div> : <div className="empty-projects">
          <Icon name="folder" size={40} />
          <h2>Tout commence par une idée.</h2>
          <p>Votre premier site n’attend que quelques mots.</p>
          <button className="primary-button" onClick={startNew}>Créer mon premier site <Icon name="arrow" size={16} />
          </button>
        </div>}</div> : <div className="home-page">
        <section className="hero">
          <h1>Les grandes idées<br />commencent <span>par quelques mots.</span>
          </h1>
          <p className="hero-subtitle">Décrivez le site que vous imaginez.<br className="mobile-break" /> Regardez-le prendre forme, en direct.</p>
          <div className="hero-composer">
            <PromptBox ref={promptRef} busy={false} onSubmit={(prompt) => void generate(prompt)} onStop={stop} value={draft} onChange={setDraft} />
            <div className="suggestions">{suggestions.map((suggestion) =>
              <button key={suggestion.label} onClick={() => selectInspiration(suggestion.prompt)}>
                <Icon name={suggestion.icon} size={14} />{suggestion.label}<span>↗</span>
              </button>)}</div>
            <p className="prompt-hint">
              <span />Un aperçu en direct. Du code qui vous appartient.</p>
          </div>
        </section>
        <section className="inspiration-section">
          <div className="inspiration-heading">
            <div>
              <h2>Un peu d’inspiration ?</h2>
              <p>Un point de départ pour votre prochaine grande idée.</p>
            </div>
            <span>IMAGINEZ LA SUITE <span>↘</span>
            </span>
          </div>
          <div className="inspiration-grid">{inspirations.map((inspiration) =>
            <button className="inspiration-card" key={inspiration.theme} onClick={() => selectInspiration(inspiration.prompt)}>
              <InspirationArt theme={inspiration.theme} />
              <div className="inspiration-card-footer">
                <div>
                  <span>{inspiration.category}</span>
                  <h3>{inspiration.name}</h3>
                </div>
                <span className="card-arrow">↗</span>
              </div>
            </button>)}</div>
        </section>
        {state.error && <div className="error-notice home-error" role="alert">{state.error}</div>}
        <footer className="home-footer">
          <BrandMark small />
          <span>Moins de barrières. Plus de création.</span>
          <span className="footer-stack">HTML · CSS · JavaScript</span>
        </footer>
      </div>}
    </main>
  </div>;
}
