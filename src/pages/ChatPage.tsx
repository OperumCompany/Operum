import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import {
  Bot,
  ExternalLink,
  History,
  LoaderCircle,
  MessageSquarePlus,
  Pencil,
  Send,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../context/AuthContext';
import { usePortfolios } from '../context/PortfoliosContext';
import { ChatConversation, ChatMessage, ConversationMessageResponse } from '../types';
import { getActivePortfolioSelectionLabel } from '../utils/portfolios';
import { getScopedStorageKey, storageKeys } from '../utils/storage';
import api from '../utils/api';

const suggestions = [
  'O que é renda variável e quais são seus principais riscos?',
  'Como juros e inflação afetam diferentes investimentos?',
  'Como identificar concentração na carteira?',
  'Como está a composição da minha carteira ativa?',
];

type ConversationGroup = {
  label: string;
  conversations: ChatConversation[];
};

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function groupConversations(conversations: ChatConversation[]): ConversationGroup[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const groups: Record<'today' | 'week' | 'older', ChatConversation[]> = {
    today: [],
    week: [],
    older: [],
  };

  conversations.forEach((conversation) => {
    const updated = new Date(conversation.updated_at);
    updated.setHours(0, 0, 0, 0);
    const elapsedDays = Math.floor((today.getTime() - updated.getTime()) / 86_400_000);
    if (elapsedDays <= 0) groups.today.push(conversation);
    else if (elapsedDays <= 7) groups.week.push(conversation);
    else groups.older.push(conversation);
  });

  return [
    { label: 'Hoje', conversations: groups.today },
    { label: 'Últimos 7 dias', conversations: groups.week },
    { label: 'Anteriores', conversations: groups.older },
  ].filter((group) => group.conversations.length > 0);
}

export function ChatPage() {
  const { user } = useAuth();
  const { activePortfolio, isAllPortfoliosSelected } = usePortfolios();
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [mobileHistoryOpen, setMobileHistoryOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const messageEndRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const skipMessageLoadForIdRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadConversations() {
      setConversationsLoading(true);
      setError('');
      try {
        const data = await api.get<ChatConversation[]>('/chat/conversations');
        if (cancelled) return;
        setConversations(data);
        setActiveId(data[0]?.id ?? null);
        if (user?.id) localStorage.removeItem(getScopedStorageKey(storageKeys.chat, user.id));
      } catch {
        if (!cancelled) setError('Não foi possível carregar suas conversas.');
      } finally {
        if (!cancelled) setConversationsLoading(false);
      }
    }
    void loadConversations();
    return () => { cancelled = true; };
  }, [user?.id]);

  useEffect(() => {
    let cancelled = false;
    async function loadMessages() {
      if (!activeId) {
        setMessages([]);
        setMessagesLoading(false);
        return;
      }
      if (skipMessageLoadForIdRef.current === activeId) {
        skipMessageLoadForIdRef.current = null;
        setMessagesLoading(false);
        return;
      }
      setMessages([]);
      setMessagesLoading(true);
      setError('');
      try {
        const data = await api.get<ChatMessage[]>(`/chat/conversations/${activeId}/messages`);
        if (!cancelled) setMessages(data);
      } catch {
        if (!cancelled) setError('A conversa não está disponível.');
      } finally {
        if (!cancelled) setMessagesLoading(false);
      }
    }
    void loadMessages();
    return () => { cancelled = true; };
  }, [activeId]);

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    messageEndRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' });
  }, [messages, sending]);

  useEffect(() => {
    const composer = composerRef.current;
    if (!composer) return;
    composer.style.height = 'auto';
    composer.style.height = `${Math.min(composer.scrollHeight, 144)}px`;
  }, [text]);

  useEffect(() => {
    if (!mobileHistoryOpen) return;
    function closeOnEscape(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') setMobileHistoryOpen(false);
    }
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [mobileHistoryOpen]);

  async function createConversation(skipInitialMessageLoad = false) {
    const conversation = await api.post<ChatConversation>('/chat/conversations', {
      portfolio_id: isAllPortfoliosSelected ? null : activePortfolio?.id ?? null,
      use_all_portfolios: isAllPortfoliosSelected,
    });
    setConversations((current) => [conversation, ...current.filter((item) => item.id !== conversation.id)]);
    if (skipInitialMessageLoad) skipMessageLoadForIdRef.current = conversation.id;
    setActiveId(conversation.id);
    setMessages([]);
    setError('');
    setMobileHistoryOpen(false);
    return conversation;
  }

  async function startNewConversation() {
    try {
      await createConversation();
      window.setTimeout(() => composerRef.current?.focus(), 0);
    } catch {
      setError('Não foi possível criar uma nova conversa.');
    }
  }

  function beginRename(conversation: ChatConversation) {
    setEditingId(conversation.id);
    setEditingTitle(conversation.title);
  }

  async function saveRename(conversation: ChatConversation) {
    const nextTitle = editingTitle.trim();
    if (!nextTitle || nextTitle === conversation.title) {
      setEditingId(null);
      return;
    }
    try {
      const updated = await api.patch<ChatConversation>(`/chat/conversations/${conversation.id}`, { title: nextTitle });
      setConversations((current) => current.map((item) => item.id === updated.id ? updated : item));
      setEditingId(null);
    } catch {
      setError('Não foi possível renomear a conversa.');
    }
  }

  async function deleteConversation(conversation: ChatConversation) {
    if (!window.confirm(`Excluir a conversa “${conversation.title}”?`)) return;
    try {
      await api.del<{ status: string }>(`/chat/conversations/${conversation.id}`);
      const remaining = conversations.filter((item) => item.id !== conversation.id);
      setConversations(remaining);
      if (activeId === conversation.id) {
        setActiveId(remaining[0]?.id ?? null);
        setMessages([]);
      }
    } catch {
      setError('Não foi possível excluir a conversa.');
    }
  }

  async function send(content: string) {
    const clean = content.trim();
    if (!clean || sending) return;
    setSending(true);
    setError('');
    setText('');
    try {
      const conversation = activeId
        ? conversations.find((item) => item.id === activeId) ?? await createConversation(true)
        : await createConversation(true);
      const optimistic: ChatMessage = {
        id: crypto.randomUUID(), role: 'user', content: clean, created_at: new Date().toISOString(),
      };
      setMessages((current) => [...current, optimistic]);
      const response = await api.post<ConversationMessageResponse>(`/chat/conversations/${conversation.id}/messages`, {
        content: clean,
        portfolio_id: isAllPortfoliosSelected ? null : activePortfolio?.id ?? null,
        use_all_portfolios: isAllPortfoliosSelected,
      });
      setMessages((current) => [...current.filter((item) => item.id !== optimistic.id), response.user_message, response.assistant_message]);
      setConversations((current) => [
        response.conversation,
        ...current.filter((item) => item.id !== response.conversation.id),
      ]);
      setActiveId(response.conversation.id);
    } catch {
      setText(clean);
      setError('Não consegui gerar a resposta agora. Sua pergunta foi restaurada para você tentar novamente.');
    } finally {
      setSending(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(text);
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send(text);
    }
  }

  const activeConversation = conversations.find((item) => item.id === activeId);
  const conversationGroups = useMemo(() => groupConversations(conversations), [conversations]);
  const portfolioContext = getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected);
  const userInitial = user?.name?.trim().charAt(0).toUpperCase() || 'V';

  const historyPanel = (
    <aside className="chat-history-panel" aria-label="Histórico de conversas">
      <div className="chat-history-mobile-heading">
        <p>Suas conversas</p>
        <button type="button" onClick={() => setMobileHistoryOpen(false)} aria-label="Fechar histórico"><X size={19} /></button>
      </div>
      <button type="button" className="chat-new-button" onClick={() => void startNewConversation()}>
        <MessageSquarePlus size={18} />
        Novo chat
      </button>

      <div className="chat-history-scroll">
        {conversationsLoading && conversations.length === 0 && (
          <div className="chat-history-status"><LoaderCircle className="animate-spin" size={17} /> Carregando histórico...</div>
        )}
        {!conversationsLoading && conversations.length === 0 && (
          <p className="chat-history-empty">Nenhuma conversa ainda. Crie um chat para começar.</p>
        )}
        {conversationGroups.map((group) => (
          <section key={group.label} className="chat-history-group">
            <h2>{group.label}</h2>
            <div>
              {group.conversations.map((conversation) => {
                const isActive = activeId === conversation.id;
                const isEditing = editingId === conversation.id;
                return (
                  <div key={conversation.id} className={`chat-history-item ${isActive ? 'is-active' : ''}`}>
                    {isEditing ? (
                      <input
                        autoFocus
                        value={editingTitle}
                        onChange={(event) => setEditingTitle(event.target.value)}
                        onBlur={() => void saveRename(conversation)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') void saveRename(conversation);
                          if (event.key === 'Escape') setEditingId(null);
                        }}
                        aria-label="Título da conversa"
                        maxLength={120}
                      />
                    ) : (
                      <button
                        type="button"
                        className="chat-history-select"
                        onClick={() => { setActiveId(conversation.id); setMobileHistoryOpen(false); }}
                        aria-current={isActive ? 'true' : undefined}
                      >
                        <span>{conversation.title}</span>
                        <small>{conversation.message_count} mensagens</small>
                      </button>
                    )}
                    {!isEditing && (
                      <div className="chat-history-actions">
                        <button type="button" onClick={() => beginRename(conversation)} aria-label={`Renomear ${conversation.title}`}><Pencil size={13} /></button>
                        <button type="button" className="is-danger" onClick={() => void deleteConversation(conversation)} aria-label={`Excluir ${conversation.title}`}><Trash2 size={13} /></button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </aside>
  );

  return (
    <div className="chat-workspace">
      <div className="chat-history-desktop">{historyPanel}</div>

      {mobileHistoryOpen && (
        <div className="chat-history-overlay" role="presentation">
          <button type="button" className="chat-history-backdrop" onClick={() => setMobileHistoryOpen(false)} aria-label="Fechar histórico" />
          <div className="chat-history-drawer" role="dialog" aria-modal="true" aria-label="Histórico de conversas">{historyPanel}</div>
        </div>
      )}

      <section className="chat-conversation-panel">
        <header className="chat-conversation-header">
          <button type="button" className="chat-mobile-history-button" onClick={() => setMobileHistoryOpen(true)} aria-label="Abrir histórico de conversas">
            <History size={19} />
          </button>
          <span className="chat-agent-icon"><Sparkles size={18} /></span>
          <div className="chat-conversation-heading">
            <h1>{activeConversation?.title ?? 'Agente financeiro Operum'}</h1>
            <p><span aria-hidden="true" />Contexto: {portfolioContext}</p>
          </div>
        </header>

        <div className="chat-messages" aria-live="polite" aria-busy={messagesLoading || sending}>
          <div className="chat-message-column">
            {messagesLoading && (
              <div className="chat-loading-state"><LoaderCircle className="animate-spin" size={20} /> Carregando conversa...</div>
            )}

            {!messagesLoading && messages.length === 0 && (
              <div className="chat-empty-state">
                <span className="chat-empty-icon"><Bot size={24} /></span>
                <p className="eyebrow">Operum IA</p>
                <h2>O que você quer entender?</h2>
                <p>Consulte conceitos, notícias e o contexto da sua carteira em uma conversa educativa e direta.</p>
                <div className="chat-suggestions">
                  {suggestions.map((suggestion) => (
                    <button type="button" key={suggestion} onClick={() => void send(suggestion)} disabled={sending}>{suggestion}</button>
                  ))}
                </div>
              </div>
            )}

            {!messagesLoading && messages.map((message) => {
              const isAssistant = message.role === 'assistant';
              return (
                <article key={message.id} className={`chat-message ${isAssistant ? 'is-assistant' : 'is-user'}`}>
                  <div className={`chat-message-avatar ${isAssistant ? 'is-agent' : ''}`} aria-hidden="true">
                    {isAssistant ? <Bot size={17} /> : userInitial}
                  </div>
                  <div className="chat-message-body">
                    <div className="chat-message-meta">
                      <strong>{isAssistant ? 'Operum IA' : user?.name || 'Você'}</strong>
                      <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
                    </div>
                    {isAssistant ? (
                      <div className="chat-markdown"><ReactMarkdown>{message.content}</ReactMarkdown></div>
                    ) : (
                      <p className="chat-user-copy">{message.content}</p>
                    )}
                    {isAssistant && !!message.sources?.length && (
                      <div className="chat-sources">
                        <p>Fontes consultadas</p>
                        <div>
                          {message.sources.map((source) => (
                            <a key={`${message.id}-${source.id}`} href={source.source_url} target="_blank" rel="noreferrer">
                              <span>{source.title || source.source_name}</span><ExternalLink size={12} />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </article>
              );
            })}

            {sending && (
              <div className="chat-message is-assistant chat-thinking">
                <div className="chat-message-avatar is-agent"><Bot size={17} /></div>
                <div className="chat-message-body">
                  <div className="chat-message-meta"><strong>Operum IA</strong><span>analisando</span></div>
                  <p><i /><i /><i /></p>
                </div>
              </div>
            )}
            <div ref={messageEndRef} />
          </div>
        </div>

        <footer className="chat-composer-area">
          <div className="chat-composer-column">
            {error && <p className="chat-error" role="alert">{error}</p>}
            <form onSubmit={onSubmit} className="chat-command-bar">
              <textarea
                ref={composerRef}
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={onComposerKeyDown}
                placeholder="Pergunte à Operum IA..."
                disabled={sending}
                rows={1}
                aria-label="Mensagem para a Operum IA"
              />
              <button type="submit" disabled={sending || !text.trim()} aria-label="Enviar mensagem">
                {sending ? <LoaderCircle className="animate-spin" size={19} /> : <Send size={19} />}
              </button>
            </form>
            <p className="chat-disclaimer">A Operum IA pode cometer erros. Verifique informações financeiras importantes.</p>
          </div>
        </footer>
      </section>
    </div>
  );
}
