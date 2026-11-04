"use client";

import {
  CircleNotch,
  MusicNote,
  BookOpen,
  CaretDown,
  ArrowClockwise,
} from "@phosphor-icons/react";
import Markdown from "react-markdown";
import type { MessageJob, Turn } from "@/lib/api";

export function Welcome() {
  return (
    <div className="welcome-message">
      <span className="message-avatar" aria-hidden="true">
        <MusicNote size={20} weight="light" />
      </span>
      <div>
        <p className="message-author">ASSISTENTE DO EMPÓRIO</p>
        <p className="welcome-copy">
          Um bom instrumento começa
          <br className="desktop-break" /> com uma boa conversa.
        </p>
        <p className="welcome-description">
          Encontre seu próximo instrumento, consulte seu pedido
          <br className="desktop-break" /> ou tire dúvidas sobre a loja. Por
          onde começamos?
        </p>
      </div>
    </div>
  );
}

function TurnMessage({
  turn,
  onRetry,
  disabled,
}: {
  turn: Turn;
  onRetry: (text: string) => void;
  disabled: boolean;
}) {
  return (
    <article className="conversation-turn">
      <div className="user-message">
        <span className="sr-only">Você: </span>
        {turn.user_message}
      </div>
      <div
        className={`assistant-message ${turn.status !== "ok" ? "reply-warning" : ""}`}
      >
        <span className="message-avatar" aria-hidden="true">
          <MusicNote size={19} weight="light" />
        </span>
        <div className="reply-body">
          <p className="message-author">ASSISTENTE DO EMPÓRIO</p>
          <div className="reply-copy">
            <Markdown
              skipHtml
              allowedElements={[
                "p",
                "strong",
                "em",
                "ul",
                "ol",
                "li",
                "br",
                "blockquote",
                "code",
                "h3",
                "h4",
              ]}
              unwrapDisallowed
            >
              {turn.text}
            </Markdown>
          </div>
          {turn.sources.length > 0 && (
            <details className="sources">
              <summary>
                <BookOpen size={15} /> Fontes consultadas{" "}
                <CaretDown size={12} />
              </summary>
              <ul>
                {turn.sources.map((source) => (
                  <li
                    key={`${source.source}-${source.version}-${source.page}-${source.section}`}
                  >
                    <strong>{source.section}</strong>
                    <span>
                      {source.source} · p. {source.page} · versão{" "}
                      {source.version}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {turn.status !== "ok" && (
            <button
              type="button"
              className="text-button retry-turn"
              disabled={disabled}
              onClick={() => onRetry(turn.user_message)}
            >
              <ArrowClockwise size={14} /> Tentar outra resposta
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

export function ChatThread({
  turns,
  job,
  waiting,
  slow,
  disabled,
  onRetry,
}: {
  turns: Turn[];
  job: MessageJob | null;
  waiting: boolean;
  slow: boolean;
  disabled: boolean;
  onRetry: (text: string) => void;
}) {
  return (
    <div
      className="thread"
      role="log"
      aria-label="Conversa com o Empório da Música"
      aria-live="polite"
      aria-relevant="additions"
    >
      {turns.map((turn) => (
        <TurnMessage
          key={turn.id}
          turn={turn}
          onRetry={onRetry}
          disabled={disabled}
        />
      ))}
      {job && (
        <div className="conversation-turn">
          <div className="user-message">
            <span className="sr-only">Você: </span>
            {job.text}
          </div>
          <div className="assistant-message pending-message" role="status">
            <span className="message-avatar" aria-hidden="true">
              <CircleNotch size={19} className={waiting ? "spin" : ""} />
            </span>
            <div>
              <p>
                {waiting
                  ? "Preparando sua resposta"
                  : "Envio ainda não confirmado"}
                <span className="waiting-dots" aria-hidden="true">
                  {waiting ? "…" : ""}
                </span>
              </p>
              {slow && waiting && (
                <small>
                  A resposta está levando um pouco mais de tempo. Você pode
                  aguardar aqui.
                </small>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
