"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import {
  ArrowUp,
  ArrowRight,
  ArrowClockwise,
  ClockCounterClockwise,
  CircleNotch,
  Key,
  MusicNotes,
  Pause,
  Play,
  Plus,
  SignOut,
  Sparkle,
  WarningCircle,
} from "@phosphor-icons/react";
import { useStoreChat } from "@/lib/use-store-chat";
import { Brand, MusicalBackdrop } from "./brand";
import { ChatThread, Welcome } from "./chat-thread";
import { HistoryDialog } from "./history-dialog";

const SUGGESTIONS = [
  "Violões até R$ 1.000",
  "Consultar um pedido",
  "Trocas e devoluções",
];

function AccessForm({
  onLogin,
  disabled,
  loading,
  cooldown,
}: {
  onLogin: (token: string) => Promise<boolean | undefined>;
  disabled: boolean;
  loading: boolean;
  cooldown: number;
}) {
  const [token, setToken] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!token.trim() || disabled) return;
    if (await onLogin(token.trim())) setToken("");
  }
  return (
    <form className="access-form" onSubmit={submit}>
      <div className="access-intro">
        <Key size={17} weight="light" />
        <p>
          <strong>Seu acesso à demonstração</strong>
          <span>Use o código recebido para iniciar uma conversa privada.</span>
        </p>
      </div>
      <div className="access-fields">
        <label className="sr-only" htmlFor="access-token">
          Código de acesso à demonstração
        </label>
        <input
          id="access-token"
          type="password"
          autoComplete="off"
          maxLength={128}
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Cole seu código de acesso"
          disabled={disabled}
          required
        />
        <button
          className="primary-button"
          disabled={disabled || !token.trim()}
          type="submit"
        >
          {loading ? <CircleNotch size={17} className="spin" /> : null}
          {cooldown
            ? `Aguarde ${cooldown}s`
            : loading
              ? "Entrando…"
              : "Começar conversa"}
          {!loading && !cooldown && <ArrowRight size={16} />}
        </button>
      </div>
      <p className="access-note">
        O acesso é demonstrativo. Seu código não fica salvo neste dispositivo.
      </p>
    </form>
  );
}

export default function StoreChat() {
  const chat = useStoreChat();
  const [motionPaused, setMotionPaused] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const authenticated = Boolean(chat.session?.authenticated);
  const busy = Boolean(chat.busy);
  const hasMessages = chat.turns.length > 0 || Boolean(chat.job);

  useEffect(() => {
    if (hasMessages)
      end.current?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [chat.turns.length, chat.job, hasMessages]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (chat.job || busy) return;
    void chat.send(chat.draft);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      submit();
    }
  }

  function chooseSuggestion(suggestion: string) {
    chat.setDraft(
      suggestion === SUGGESTIONS[0]
        ? "Quais violões disponíveis até R$ 1000?"
        : suggestion === SUGGESTIONS[1]
          ? "Quero consultar um pedido."
          : "Como funcionam as trocas e devoluções?",
    );
    if (authenticated) composer.current?.focus();
    else document.getElementById("access-token")?.focus();
  }

  function openHistory() {
    dialog.current?.showModal();
    void chat.loadConversations();
  }

  return (
    <main className="stage" data-motion={motionPaused ? "off" : "on"}>
      <a className="skip-link" href="#message-input">
        Ir para a mensagem
      </a>
      <MusicalBackdrop />
      <div className="page-content">
        <Brand />
        <section
          className={`chat-panel ${hasMessages ? "has-messages" : ""}`}
          aria-label="Atendimento do Empório da Música"
        >
          <header className="panel-header">
            <div className="assistant-identity">
              <span className="assistant-seal" aria-hidden="true">
                <Sparkle size={21} weight="light" />
              </span>
              <div>
                <h2>Assistente do Empório</h2>
                <p className="session-indicator">
                  <span aria-hidden="true" />
                  {chat.busy === "boot"
                    ? "Conectando ao atendimento"
                    : authenticated
                      ? "Sessão demonstrativa"
                      : "Um espaço para a sua música"}
                </p>
              </div>
            </div>
            <nav className="panel-actions" aria-label="Ações da conversa">
              <button
                type="button"
                className="header-button"
                onClick={openHistory}
                disabled={!authenticated || busy}
                title="Histórico de conversas"
              >
                <ClockCounterClockwise size={19} weight="light" />
                <span>Histórico</span>
              </button>
              <button
                type="button"
                className="header-button"
                onClick={chat.newConversation}
                disabled={!authenticated || busy}
                title="Nova conversa"
              >
                <Plus size={19} weight="light" />
                <span>Nova conversa</span>
              </button>
              {authenticated && (
                <button
                  type="button"
                  className="icon-button logout-button"
                  onClick={() => void chat.logout()}
                  disabled={busy}
                  aria-label="Encerrar sessão"
                  title="Encerrar sessão"
                >
                  <SignOut size={19} weight="light" />
                </button>
              )}
            </nav>
          </header>

          <div className="chat-content">
            {!hasMessages && <Welcome />}
            {hasMessages && (
              <ChatThread
                turns={chat.turns}
                job={chat.job}
                waiting={chat.busy === "send"}
                slow={chat.slow}
                disabled={
                  busy ||
                  Boolean(chat.job) ||
                  Boolean(chat.cooldown) ||
                  chat.conversationFull
                }
                onRetry={(text) => void chat.send(text)}
              />
            )}
            <div ref={end} />
            {chat.busy === "boot" && (
              <p className="connection-status" role="status">
                <CircleNotch size={17} className="spin" /> Preparando seu
                espaço…
              </p>
            )}
            {!authenticated && chat.busy !== "boot" && chat.session && (
              <AccessForm
                onLogin={chat.login}
                disabled={busy || Boolean(chat.cooldown)}
                loading={chat.busy === "login"}
                cooldown={chat.cooldown}
              />
            )}
            {(chat.error || (chat.job && chat.busy !== "send")) && (
              <div className="error-notice" role="alert">
                <WarningCircle size={19} weight="light" />
                <div>
                  <p>{chat.error || "O envio ainda não foi confirmado. Você pode tentar novamente sem duplicá-lo."}</p>
                  <div className="error-actions">
                    {chat.job && (
                      <>
                        <button
                          className="text-button"
                          disabled={busy || Boolean(chat.cooldown)}
                          onClick={() => void chat.send(chat.job!.text, true)}
                        >
                          <ArrowClockwise size={14} />
                          {chat.cooldown
                            ? `Tentar em ${chat.cooldown}s`
                            : "Tentar novamente"}
                        </button>
                        <button
                          className="text-button"
                          disabled={busy || Boolean(chat.cooldown)}
                          onClick={() => void chat.confirmHistory()}
                        >
                          Conferir histórico
                        </button>
                      </>
                    )}
                    {!chat.job && (
                      <button
                        className="text-button"
                        disabled={busy || Boolean(chat.cooldown)}
                        onClick={() => void chat.bootstrap()}
                      >
                        <ArrowClockwise size={14} />
                        {chat.cooldown
                          ? `Aguarde ${chat.cooldown}s`
                          : "Reconectar"}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="composer-area">
            {!hasMessages && (
              <div className="suggestions" aria-label="Sugestões de perguntas">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    type="button"
                    disabled={busy}
                    key={suggestion}
                    onClick={() => chooseSuggestion(suggestion)}
                  >
                    {suggestion}
                    <ArrowRight size={13} />
                  </button>
                ))}
              </div>
            )}
            {chat.conversationFull ? (
              <div className="conversation-limit">
                <p>Uma nova conversa para continuar sua descoberta.</p>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={chat.newConversation}
                >
                  Começar nova conversa <Plus size={16} />
                </button>
              </div>
            ) : (
              <form className="composer-form" onSubmit={submit}>
                <label htmlFor="message-input">SUA MENSAGEM</label>
                <div className="composer-box">
                  <textarea
                    ref={composer}
                    id="message-input"
                    rows={2}
                    maxLength={2000}
                    value={chat.draft}
                    onChange={(event) => chat.setDraft(event.target.value)}
                    onKeyDown={onKeyDown}
                    placeholder="Pergunte sobre instrumentos, preços, pedidos ou políticas…"
                    disabled={busy || Boolean(chat.job)}
                    aria-describedby="composer-help"
                  />
                  <button
                    className="send-button"
                    type="submit"
                    aria-label="Enviar mensagem"
                    disabled={
                      !authenticated ||
                      busy ||
                      Boolean(chat.job) ||
                      !chat.draft.trim() ||
                      Boolean(chat.cooldown)
                    }
                  >
                    <ArrowUp size={23} weight="regular" />
                  </button>
                </div>
                <div className="composer-meta" id="composer-help">
                  <span>
                    {authenticated
                      ? "Atendimento por IA. Confira as informações importantes."
                      : "Entre na demonstração para enviar sua mensagem."}
                  </span>
                  <span>
                    {chat.draft.length > 1600
                      ? `${chat.draft.length}/2.000`
                      : "Enter para enviar · Shift + Enter para nova linha"}
                  </span>
                </div>
              </form>
            )}
          </div>
        </section>
        <footer className="page-footer">
          <p>
            ESCOLHA COM CURIOSIDADE{" "}
            <MusicNotes size={13} weight="thin" aria-hidden="true" /> TOQUE COM
            PERSONALIDADE
          </p>
          <button
            type="button"
            className="motion-toggle"
            onClick={() => setMotionPaused((value) => !value)}
            aria-pressed={motionPaused}
          >
            {motionPaused ? <Play size={12} /> : <Pause size={12} />}
            {motionPaused ? "Retomar movimento" : "Pausar movimento"}
          </button>
        </footer>
      </div>
      <HistoryDialog
        ref={dialog}
        conversations={chat.conversations}
        selected={chat.selected}
        loading={chat.busy === "history"}
        hasMore={chat.hasMore}
        error={chat.busy !== "history" ? chat.error : ""}
        onMore={() => void chat.loadConversations(true)}
        onSelect={(id) =>
          void chat.selectConversation(id).then((success) => {
            if (success) dialog.current?.close();
          })
        }
      />
    </main>
  );
}
