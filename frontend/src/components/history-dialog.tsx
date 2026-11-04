"use client";

import { forwardRef } from "react";
import {
  ClockCounterClockwise,
  X,
  ChatCircle,
  ArrowRight,
  CircleNotch,
} from "@phosphor-icons/react";
import type { Conversation } from "@/lib/api";

const dateFormat = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export const HistoryDialog = forwardRef<
  HTMLDialogElement,
  {
    conversations: Conversation[];
    selected: string | null;
    loading: boolean;
    hasMore: boolean;
    error: string;
    onSelect: (id: string) => void;
    onMore: () => void;
  }
>(function HistoryDialog(
  { conversations, selected, loading, hasMore, error, onSelect, onMore },
  ref,
) {
  return (
    <dialog
      ref={ref}
      className="history-dialog"
      aria-labelledby="history-title"
    >
      <div className="dialog-heading">
        <div>
          <p className="eyebrow">CADA CONVERSA, UM COMEÇO</p>
          <h2 id="history-title">
            <ClockCounterClockwise size={24} weight="light" /> Suas conversas
          </h2>
        </div>
        <form method="dialog">
          <button className="icon-button" aria-label="Fechar histórico">
            <X size={20} />
          </button>
        </form>
      </div>
      <p className="dialog-description">
        Conversas salvas nesta sessão de acesso.
      </p>
      {error && (
        <p role="alert" className="inline-error">
          {error}
        </p>
      )}
      {!loading && !error && conversations.length === 0 && (
        <div className="history-empty">
          <ChatCircle size={32} weight="thin" />
          <p>Sua primeira conversa começa aqui.</p>
        </div>
      )}
      <ul className="history-list">
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <button
              type="button"
              onClick={() => onSelect(conversation.id)}
              disabled={loading}
              aria-current={selected === conversation.id ? "true" : undefined}
            >
              <ChatCircle size={21} weight="light" />
              <span>
                <strong>
                  Conversa de{" "}
                  {dateFormat.format(new Date(conversation.created_at))}
                </strong>
                <small>
                  {selected === conversation.id
                    ? "Conversa atual"
                    : "Retomar conversa"}
                </small>
              </span>
              <ArrowRight size={17} />
            </button>
          </li>
        ))}
      </ul>
      {loading && (
        <p className="dialog-loading" role="status">
          <CircleNotch className="spin" size={18} /> Buscando suas conversas…
        </p>
      )}
      {hasMore && (
        <button
          type="button"
          className="secondary-button load-more"
          disabled={loading}
          onClick={onMore}
        >
          Carregar mais conversas
        </button>
      )}
    </dialog>
  );
});
