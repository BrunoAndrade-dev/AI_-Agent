"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  StoreApi,
  type Conversation,
  type MessageJob,
  type Session,
  type Turn,
} from "./api";

type Busy = "boot" | "login" | "history" | "send" | "logout" | null;

export function useStoreChat() {
  const [api] = useState(() => new StoreApi());
  const [session, setSession] = useState<Session | null>(null);
  const [busy, setBusy] = useState<Busy>("boot");
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [job, setJob] = useState<MessageJob | null>(null);
  const [maxTurns, setMaxTurns] = useState(25);
  const [conversationFull, setConversationFull] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [slow, setSlow] = useState(false);
  const inFlight = useRef(false);
  const bootVersion = useRef(0);

  const bootstrap = useCallback(async () => {
    const version = ++bootVersion.current;
    setBusy("boot");
    setError("");
    try {
      const state = await api.session();
      if (version !== bootVersion.current) return;
      setSession(state);
      if (state.authenticated) {
        const page = await api.conversations();
        if (version !== bootVersion.current) return;
        setConversations(page.results);
        setHistoryPage(1);
        setHasMore(Boolean(page.next));
        const latest = page.results[0];
        if (latest) {
          const history = await api.history(latest.id);
          if (version !== bootVersion.current) return;
          setSelected(latest.id);
          setTurns(history.turns);
          setMaxTurns(history.max_turns);
          setConversationFull(history.turns.length >= history.max_turns);
        } else {
          setSelected(null);
          setTurns([]);
          setConversationFull(false);
        }
      } else {
        setSelected(null);
        setTurns([]);
        setConversations([]);
        setJob(null);
        setDraft("");
      }
    } catch {
      if (version === bootVersion.current)
        setError(
          "Não consegui conectar ao atendimento. Confira sua conexão e tente novamente.",
        );
    } finally {
      if (version === bootVersion.current) setBusy(null);
    }
  }, [api]);

  useEffect(() => {
    void bootstrap();
    return () => {
      bootVersion.current += 1;
    };
  }, [bootstrap]);

  useEffect(() => {
    if (busy !== "send") return;
    const timer = setTimeout(() => setSlow(true), 15000);
    return () => {
      clearTimeout(timer);
      setSlow(false);
    };
  }, [busy]);

  const coolingDown = cooldown > 0;
  useEffect(() => {
    if (!coolingDown) return;
    const timer = setInterval(
      () => setCooldown((value) => Math.max(0, value - 1)),
      1000,
    );
    return () => clearInterval(timer);
  }, [coolingDown]);

  function start(operation: Busy) {
    if (inFlight.current || busy) return false;
    inFlight.current = true;
    setBusy(operation);
    setError("");
    return true;
  }

  function finish() {
    inFlight.current = false;
    setBusy(null);
  }

  function clearPrivateState() {
    setTurns([]);
    setSelected(null);
    setConversations([]);
    setJob(null);
    setDraft("");
    setConversationFull(false);
    setHasMore(false);
  }

  function handleError(cause: unknown) {
    if (cause instanceof ApiError) {
      if (cause.status === 401 || cause.status === 403) {
        clearPrivateState();
        setSession({ authenticated: false, csrf_token: "", expires_at: null });
        setError(
          cause.status === 401
            ? "Esse acesso é inválido ou expirou. Confira o código recebido."
            : "Seu acesso precisa ser renovado. Entre novamente para continuar.",
        );
        return;
      }
      if (cause.status === 404) {
        clearPrivateState();
        setError(
          "Esta conversa não está disponível nesta sessão. Reconecte o atendimento.",
        );
        return;
      }
      if (cause.status === 429) {
        const wait = Math.min(3600, Math.ceil(cause.retryAfter || 30));
        setCooldown(wait);
        setError(
          "Vamos com calma: aguarde um instante antes de tentar novamente.",
        );
        return;
      }
      if (cause.status === 409 && cause.message.includes("25")) {
        setConversationFull(true);
        setJob(null);
        setError(
          "Esta conversa chegou ao limite de envios. Comece uma nova para continuar.",
        );
        return;
      }
      if (cause.status === 409) {
        setError(
          "Há um envio em andamento. Aguarde um instante e tente novamente.",
        );
        return;
      }
      setError(
        cause.status === 0
          ? cause.message
          : "Não foi possível concluir agora. Tente novamente.",
      );
    } else setError("Não foi possível concluir agora. Tente novamente.");
  }

  async function login(token: string) {
    if (cooldown || !start("login")) return;
    try {
      const state = await api.login(token);
      const waitingDraft = draft;
      clearPrivateState();
      setDraft(waitingDraft);
      setSession(state);
      return true;
    } catch (cause) {
      handleError(cause);
      return false;
    } finally {
      finish();
    }
  }

  async function logout() {
    if (!start("logout")) return;
    try {
      await api.logout();
      clearPrivateState();
      setSession({ authenticated: false, csrf_token: "", expires_at: null });
    } catch (cause) {
      handleError(cause);
    } finally {
      finish();
    }
  }

  function newConversation() {
    if (busy) return;
    setSelected(null);
    setTurns([]);
    setJob(null);
    setDraft("");
    setError("");
    setConversationFull(false);
  }

  async function loadConversations(more = false) {
    if (!start("history")) return;
    try {
      const page = await api.conversations(more ? historyPage + 1 : 1);
      setConversations((current) =>
        more ? [...current, ...page.results] : page.results,
      );
      setHistoryPage(more ? historyPage + 1 : 1);
      setHasMore(Boolean(page.next));
    } catch (cause) {
      handleError(cause);
    } finally {
      finish();
    }
  }

  async function selectConversation(id: string) {
    if (!start("history")) return false;
    try {
      const history = await api.history(id);
      setSelected(id);
      setTurns(history.turns);
      setJob(null);
      setDraft("");
      setMaxTurns(history.max_turns);
      setConversationFull(history.turns.length >= history.max_turns);
      return true;
    } catch (cause) {
      handleError(cause);
      return false;
    } finally {
      finish();
    }
  }

  async function confirmHistory() {
    if (!selected || !start("history")) return;
    try {
      const history = await api.history(selected);
      setTurns(history.turns);
      setMaxTurns(history.max_turns);
      setConversationFull(history.turns.length >= history.max_turns);
      if (
        job &&
        history.turns.some((turn) => turn.request_id === job.requestId)
      ) {
        setJob(null);
      } else if (job)
        setError(
          "O envio ainda não apareceu no histórico. Aguarde e tente novamente.",
        );
    } catch (cause) {
      handleError(cause);
    } finally {
      finish();
    }
  }

  async function send(text: string, retry = false) {
    if (
      !session?.authenticated ||
      cooldown ||
      conversationFull ||
      !text.trim() ||
      text.length > 2000 ||
      !start("send")
    )
      return;
    let outgoing = retry ? job : null;
    try {
      if (!outgoing) {
        let conversationId = selected;
        if (!conversationId) {
          const created = await api.createConversation();
          conversationId = created.id;
          setSelected(created.id);
          setConversations((current) => [created, ...current]);
        }
        outgoing = { conversationId, requestId: crypto.randomUUID(), text };
        setJob(outgoing);
        setDraft("");
      }
      const response = await api.send(outgoing);
      setTurns((current) =>
        current.some((turn) => turn.id === response.turn.id)
          ? current.map((turn) =>
              turn.id === response.turn.id ? response.turn : turn,
            )
          : [...current, response.turn],
      );
      setJob(null);
      if (turns.length + 1 >= maxTurns) setConversationFull(true);
    } catch (cause) {
      handleError(cause);
    } finally {
      finish();
    }
  }

  return {
    session,
    busy,
    error,
    draft,
    setDraft,
    turns,
    selected,
    conversations,
    hasMore,
    job,
    cooldown,
    slow,
    conversationFull,
    maxTurns,
    bootstrap,
    login,
    logout,
    newConversation,
    loadConversations,
    selectConversation,
    confirmHistory,
    send,
  };
}
