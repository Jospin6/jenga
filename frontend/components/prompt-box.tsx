"use client";

import { forwardRef, useState, type FormEvent } from "react";
import { Icon } from "./icons";

type Props = { onSubmit: (prompt: string) => void; busy: boolean; onStop: () => void; compact?: boolean; value?: string; onChange?: (value: string) => void };

export const PromptBox = forwardRef<HTMLTextAreaElement, Props>(function PromptBox({ onSubmit, busy, onStop, compact, value, onChange }, ref) {
  const [draft, setDraft] = useState("");
  const text = value ?? draft;
  const update = (next: string) => onChange ? onChange(next) : setDraft(next);
  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (busy || text.trim().length < 3) return;
    onSubmit(text);
    update("");
  };
  return <form className={`prompt-box ${compact ? "compact" : ""}`} onSubmit={submit}>
    <label className="sr-only" htmlFor={compact ? "followup-prompt" : "initial-prompt"}>{compact ? "Décrivez vos modifications" : "Décrivez le site à créer"}</label>
    <textarea ref={ref} id={compact ? "followup-prompt" : "initial-prompt"} value={text} onChange={(event) => update(event.target.value)} maxLength={12000} disabled={busy}
      placeholder={compact ? "Une idée pour la suite ?" : "Un site pour mon idée, avec…"}
      onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit(); } }} />
    <div className="prompt-bottom">
      <span className="prompt-mode">
        <Icon name="spark" size={14} />{compact ? "Demandez une modification" : "Imaginez. Décrivez. Créez."}</span>
      {busy ? <button className="submit-prompt stopping" type="button" onClick={onStop} aria-label="Arrêter la génération" title="Arrêter la génération">
        <Icon name="stop" />
      </button>
        : <button className="submit-prompt" type="submit" disabled={text.trim().length < 3} aria-label={compact ? "Envoyer la modification" : "Générer mon site"} title="Envoyer">
          <Icon name="arrow" size={21} />
        </button>}
    </div>
  </form>;
});
