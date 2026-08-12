import { FormEvent, useEffect, useRef, useState } from 'react';
import { BookOpenText, History, MessageSquarePlus, Pencil, Send, Trash2, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Button, Input } from '../components/UI';
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

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

export function ChatPage() {
  const { user } = useAuth();
  const { activePortfolio, isAllPortfoliosSelected } = usePortfolios();
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [mobileHistoryOpen, setMobileHistoryOpen] = useState(false);
  const messageEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadConversations() {
      setLoading(true);
      try {
        const data = await api.get<ChatConversation[]>('/chat/conversations');
        if (cancelled) return;
        setConversations(data);
        setActiveId(data[0]?.id ?? null);
        if (user?.id) localStorage.removeItem(getScopedStorageKey(storageKeys.chat, user.id));
      } catch {
        if (!cancelled) setError('Não foi possível carregar suas conversas.');
      } finally {
        if (!cancelled) setLoading(false);
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
        return;
      }
      setLoading(true);
      try {
        const data = await api.get<ChatMessage[]>(`/chat/conversations/${activeId}/messages`);
        if (!cancelled) setMessages(data);
      } catch {
        if (!cancelled) setError('A conversa não está disponível.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadMessages();
    return () => { cancelled = true; };
  }, [activeId]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  async function createConversation() {
    const conversation = await api.post<ChatConversation>('/chat/conversations', {
      portfolio_id: isAllPortfoliosSelected ? null : activePortfolio?.id ?? null,
      use_all_portfolios: isAllPortfoliosSelected,
    });
    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setMessages([]);
    setError('');
    return conversation;
  }

  async function renameConversation(conversation: ChatConversation) {
    const nextTitle = window.prompt('Novo título da conversa:', conversation.title)?.trim();
    if (!nextTitle || nextTitle === conversation.title) return;
    const updated = await api.patch<ChatConversation>(`/chat/conversations/${conversation.id}`, { title: nextTitle });
    setConversations((current) => current.map((item) => item.id === updated.id ? updated : item));
  }

  async function deleteConversation(conversation: ChatConversation) {
    if (!window.confirm(`Excluir a conversa “${conversation.title}”?`)) return;
    await api.del<{ status: string }>(`/chat/conversations/${conversation.id}`);
    const remaining = conversations.filter((item) => item.id !== conversation.id);
    setConversations(remaining);
    if (activeId === conversation.id) {
      setActiveId(remaining[0]?.id ?? null);
      setMessages([]);
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
        ? conversations.find((item) => item.id === activeId) ?? await createConversation()
        : await createConversation();
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
      setError('Não consegui gerar a resposta agora. Sua pergunta pode ser enviada novamente.');
    } finally {
      setSending(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(text);
  }

  const activeConversation = conversations.find((item) => item.id === activeId);

  return (
    <div className="grid min-h-[calc(100vh-9rem)] gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      <button type="button" className="flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[var(--border-soft)] bg-[var(--bg-surface)] text-sm font-semibold lg:hidden" onClick={() => setMobileHistoryOpen((current) => !current)}>
        {mobileHistoryOpen ? <X size={17} /> : <History size={17} />}{mobileHistoryOpen ? 'Fechar histórico' : 'Ver conversas'}
      </button>
      <aside className={`${mobileHistoryOpen ? 'flex' : 'hidden'} max-h-[55vh] flex-col rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface)] p-3 shadow-[var(--shadow-card)] lg:flex lg:max-h-[calc(100vh-9rem)]`}>
        <Button onClick={() => void createConversation()} className="w-full">
          <MessageSquarePlus size={17} /> Novo chat
        </Button>
        <p className="mb-2 mt-5 px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--text-muted)]">Conversas</p>
        <div className="space-y-1 overflow-y-auto">
          {loading && conversations.length === 0 && <p className="px-2 py-4 text-sm text-[var(--text-muted)]">Carregando histórico...</p>}
          {!loading && conversations.length === 0 && <p className="px-2 py-4 text-sm leading-5 text-[var(--text-muted)]">Nenhuma conversa ainda. Comece uma pergunta para criar seu primeiro chat.</p>}
          {conversations.map((conversation) => (
            <div key={conversation.id} className={`group rounded-2xl border p-2 transition ${activeId === conversation.id ? 'border-[var(--brand)] bg-[var(--accent-soft)]' : 'border-transparent hover:bg-[var(--bg-surface-strong)]'}`}>
              <button onClick={() => { setActiveId(conversation.id); setMobileHistoryOpen(false); }} className="w-full px-1 text-left">
                <p className="truncate text-sm font-semibold text-[var(--text-main)]">{conversation.title}</p>
                <p className="mt-1 text-[10px] text-[var(--text-muted)]">{conversation.message_count} mensagens</p>
              </button>
              <div className="mt-2 flex gap-1 opacity-70 transition group-hover:opacity-100">
                <button aria-label="Renomear conversa" onClick={() => void renameConversation(conversation)} className="rounded-lg p-1.5 hover:bg-white"><Pencil size={13} /></button>
                <button aria-label="Excluir conversa" onClick={() => void deleteConversation(conversation)} className="rounded-lg p-1.5 text-red-600 hover:bg-white"><Trash2 size={13} /></button>
              </div>
            </div>
          ))}
        </div>
      </aside>

      <section className="flex min-h-[70vh] flex-col overflow-hidden rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface)] shadow-[var(--shadow-card)]">
        <header className="border-b border-[var(--border-soft)] px-5 py-4 sm:px-7">
          <div className="flex items-center gap-3">
            <span className="rounded-2xl bg-[var(--accent-soft)] p-2.5"><BookOpenText size={20} /></span>
            <div>
              <h2 className="font-bold text-[var(--text-main)]">{activeConversation?.title ?? 'Agente financeiro Operum'}</h2>
              <p className="text-xs text-[var(--text-muted)]">Base financeira + {getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected)}</p>
            </div>
          </div>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-7">
          {!loading && messages.length === 0 && (
            <div className="mx-auto max-w-2xl py-10 text-center">
              <p className="text-2xl font-bold text-[var(--text-main)]">O que você quer entender?</p>
              <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-[var(--text-muted)]">Consulte conceitos, notícias e o contexto da sua carteira em uma conversa educativa e direta.</p>
              <div className="mt-7 grid gap-2 sm:grid-cols-2">
                {suggestions.map((suggestion) => <button key={suggestion} onClick={() => void send(suggestion)} className="rounded-2xl border border-[var(--border-soft)] bg-white p-4 text-left text-sm font-semibold transition hover:-translate-y-0.5 hover:border-[var(--brand)]">{suggestion}</button>)}
              </div>
            </div>
          )}
          {messages.map((message) => (
              <article key={message.id} className={`max-w-[92%] rounded-[22px] px-4 py-3 text-sm leading-6 sm:max-w-[82%] sm:px-5 ${message.role === 'user' ? 'ml-auto bg-[var(--brand)] text-white' : 'border border-[var(--border-soft)] bg-white text-[var(--text-main)]'}`}>
                {message.role === 'assistant' ? (
                  <div className="prose prose-sm max-w-none prose-headings:mb-2 prose-headings:mt-4 prose-headings:text-[var(--text-main)] prose-p:my-2 prose-li:my-0.5"><ReactMarkdown>{message.content}</ReactMarkdown></div>
                ) : <p>{message.content}</p>}
                <p className="mt-2 text-[10px] opacity-60">{formatTime(message.created_at)}</p>
              </article>
          ))}
          {sending && <div className="inline-flex rounded-[22px] border border-[var(--border-soft)] bg-white px-5 py-3 text-sm text-[var(--text-muted)]">Consultando a base financeira...</div>}
          <div ref={messageEndRef} />
        </div>

        <footer className="border-t border-[var(--border-soft)] bg-white/80 p-4 backdrop-blur sm:p-5">
          {error && <p className="mb-2 text-xs font-semibold text-red-600">{error}</p>}
          <form onSubmit={onSubmit} className="flex gap-2">
            <Input value={text} onChange={(event) => setText(event.target.value)} placeholder="Pergunte sobre investimentos, mercado ou sua carteira" disabled={sending} />
            <Button type="submit" disabled={sending || !text.trim()} aria-label="Enviar mensagem"><Send size={17} /></Button>
          </form>
          <p className="mt-2 text-center text-[10px] text-[var(--text-muted)]">Conteúdo educativo. O agente não recomenda compra ou venda.</p>
        </footer>
      </section>
    </div>
  );
}
