"use client";

import { useEffect, useRef, useState } from "react";
import { createPreviewDocument } from "@/lib/preview";
import type { Files, Status } from "@/lib/types";
import { BrandMark, Icon } from "./icons";

function highlight(line: string) {
  return line.split(/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|<\/?[\w-]+|\b(?:const|let|function|return|if|else|for|new|document|window|class|import|export|true|false|null)\b|\b\d+(?:\.\d+)?\b)/g)
    .map((part, index) =>
      <span key={index} className={/^['"]/.test(part) ? "syntax-string" : /^</.test(part) ? "syntax-tag" : /^(const|let|function|return|if|else|for|new|document|window|class|import|export|true|false|null)$/.test(part) ? "syntax-keyword" : /^\d/.test(part) ? "syntax-number" : undefined}>{part}</span>);
}

export function PreviewPanel({ files, savedFiles, status, activeFile, name }: { files: Files; savedFiles: Files; status: Status; activeFile: string; name: string }) {
  const [tab, setTab] = useState<"preview" | "code">("preview");
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [selected, setSelected] = useState("");
  const [doc, setDoc] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [copyStatus, setCopyStatus] = useState("");
  const latest = useRef({ files, savedFiles });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const paths = Object.keys(files).sort();
  const currentPath = selected && selected in files ? selected : activeFile in files ? activeFile : paths[0];
  const content = files[currentPath] || "";

  useEffect(() => {
    latest.current = { files, savedFiles };
    // Throttle rather than debounce, so a continuous token stream still renders.
    if (!timer.current) timer.current = setTimeout(() => {
      setDoc(createPreviewDocument(latest.current.files, latest.current.savedFiles));
      timer.current = null;
    }, 650);
  }, [files, savedFiles]);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    if (copyTimer.current) clearTimeout(copyTimer.current);
  }, []);

  async function copy() {
    try { await navigator.clipboard.writeText(content); setCopyStatus("Copié"); }
    catch { setCopyStatus("Copie indisponible"); }
    if (copyTimer.current) clearTimeout(copyTimer.current);
    copyTimer.current = setTimeout(() => setCopyStatus(""), 2200);
  }

  return <section className="preview-panel" aria-label="Résultat de votre génération">
    <div className="preview-toolbar">
      <div className="view-tabs" role="tablist" aria-label="Afficher le résultat">
        <button id="preview-tab" role="tab" aria-selected={tab === "preview"} aria-controls="preview-content" className={tab === "preview" ? "selected" : ""} onClick={() => setTab("preview")}>
          <Icon name="eye" size={16} />Aperçu</button>
        <button id="code-tab" role="tab" aria-selected={tab === "code"} aria-controls="code-content" className={tab === "code" ? "selected" : ""} onClick={() => setTab("code")}>
          <Icon name="code" size={16} />Code{paths.length > 0 && <span className="tab-count">{paths.length}</span>}</button>
      </div>
      <div className="preview-tools">
        {tab === "preview" && <>
          <button className={`icon-button ${device === "desktop" ? "active" : ""}`} aria-label="Vue ordinateur" aria-pressed={device === "desktop"} onClick={() => setDevice("desktop")}>
            <Icon name="monitor" size={17} />
          </button>
          <button className={`icon-button ${device === "mobile" ? "active" : ""}`} aria-label="Vue mobile" aria-pressed={device === "mobile"} onClick={() => setDevice("mobile")}>
            <Icon name="phone" size={17} />
          </button>
          <span className="toolbar-divider" />
          <button className="icon-button" aria-label="Actualiser l’aperçu" disabled={!doc} onClick={() => setRefresh((value) => value + 1)}>
            <Icon name="refresh" size={16} />
          </button>
        </>}
        <span className={`live-indicator ${status === "generating" ? "streaming" : ""}`}>
          <i />{status === "generating" ? "En direct" : "Aperçu"}</span>
      </div>
    </div>
    {tab === "preview" ? <div id="preview-content" role="tabpanel" aria-labelledby="preview-tab" className={`preview-stage ${device}`}>
      {doc ? <div className="browser-frame">
        <div className="browser-address">
          <span className="browser-dots">
            <i />
            <i />
            <i />
          </span>
          <span>
            <Icon name="globe" size={12} />{name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "mon-site"}.preview</span>
          <span className="browser-address-label">index.html</span>
        </div>
        <iframe key={refresh} title="Aperçu du site généré" srcDoc={doc} sandbox="allow-scripts" referrerPolicy="no-referrer" />
      </div>
        : <div className="preview-empty">
          <div className="preview-empty-art">
            <span />
            <BrandMark />
            <span />
          </div>
          <span className="eyebrow">DE L’IDÉE À L’ÉCRAN</span>
          <h2>{status === "generating" ? "Votre site prend forme." : "Votre prochaine idée commence ici."}</h2>
          <p>{status === "generating" ? "L’aperçu apparaîtra dès les premières lignes de HTML. Vous pouvez déjà suivre les fichiers dans l’onglet Code." : "Décrivez votre site dans la conversation. Son aperçu apparaîtra dans cet espace."}</p>{status === "generating" && <div className="thinking-dots">
            <i />
            <i />
            <i />
          </div>}</div>}
    </div> : <div id="code-content" role="tabpanel" aria-labelledby="code-tab" className="code-workspace">
      <aside className="file-explorer">
        <div className="explorer-heading">FICHIERS <span>{paths.length}</span>
        </div>{paths.length ? paths.map((path) =>
          <button key={path} className={`file-row ${path === currentPath ? "selected" : ""}`} onClick={() => setSelected(path)} title={path}>
            <Icon name="file" size={15} />
            <span>{path}</span>{status === "generating" && path === activeFile && <i className="file-writing" />}</button>) : <p className="muted empty-files">Les fichiers apparaîtront ici.</p>}</aside>
      <div className="code-editor">
        <div className="code-heading">
          <span>
            <Icon name="code" size={14} />{currentPath || "Aucun fichier"}</span>
          <button className="text-button" onClick={copy} disabled={!currentPath}>
            <Icon name={copyStatus === "Copié" ? "check" : "copy"} size={14} />{copyStatus || "Copier"}</button>
        </div>
        {currentPath ? <pre className="code-source" tabIndex={0} aria-label={`Code de ${currentPath}`}>
          <code>{content.split("\n").map((line, index) =>
            <span className="code-line" key={index}>
              <span className="line-number" aria-hidden="true">{index + 1}</span>
              <span>{highlight(line)}{"\n"}</span>
            </span>)}</code>
        </pre> : <div className="code-placeholder">
          <Icon name="code" size={32} />
          <p>Le code s’affiche au fil de la génération.</p>
        </div>}
        <div className="editor-status">
          <span>{currentPath?.split(".").pop()?.toUpperCase() || "CODE"}</span>
          <span>{content ? content.split("\n").length : 0} lignes · Lecture seule</span>
          <span>UTF-8</span>
        </div>
      </div>
    </div>}
  </section>;
}
