"use client";

import {
  MusicNote,
  MusicNotes,
  PianoKeys,
  Sparkle,
} from "@phosphor-icons/react";

export function MusicalBackdrop() {
  return (
    <div className="musical-backdrop" aria-hidden="true">
      <span className="floating-note note-one">
        <MusicNote size={42} weight="thin" />
      </span>
      <span className="floating-note note-two">
        <MusicNotes size={30} weight="thin" />
      </span>
      <span className="floating-note note-three">
        <MusicNote size={23} weight="thin" />
      </span>
      <span className="floating-note note-four">
        <PianoKeys size={38} weight="thin" />
      </span>
      <span className="floating-note note-five">
        <MusicNotes size={47} weight="thin" />
      </span>
      <span className="floating-note note-six">
        <MusicNote size={26} weight="thin" />
      </span>
    </div>
  );
}

export function Brand() {
  return (
    <header className="brand">
      <div className="brand-emblem" aria-hidden="true">
        <i />
        <MusicNotes size={27} weight="thin" />
        <i />
      </div>
      <p className="eyebrow">ATENDIMENTO MUSICAL INTELIGENTE</p>
      <h1>
        Empório <em>da</em> Música<span>.</span>
      </h1>
      <p className="brand-slogan">Sua música começa aqui.</p>
      <div className="brand-divider" aria-hidden="true">
        <i />
        <Sparkle size={11} weight="fill" />
        <i />
      </div>
    </header>
  );
}
