import { FormEvent, useEffect, useMemo, useState } from 'react';
import { BookOpenText } from 'lucide-react';
import { Button, Card, Input } from '../components/UI';
import { useAuth } from '../context/AuthContext';
import { usePortfolios } from '../context/PortfoliosContext';
import { ChatApiResponse, ChatMessage } from '../types';
import { getScopedStorageKey, readStorage, storageKeys, writeStorage } from '../utils/storage';
import { getActivePortfolioSelectionLabel, getPortfolioLabel } from '../utils/portfolios';
import api from '../utils/api';

const suggestions = ['O que e renda variavel?', 'O que e inflacao?', 'O que significa liquidez?', 'Como esta a carteira ativa?'];
const initialGuide: ChatMessage[] = [
  {
    id: 'guide-1',
    role: 'assistant',
    content: 'Este espaco funciona como um guia rapido. Voce pode tirar duvidas basicas de investimentos e pedir um resumo educativo da carteira ativa.',
    createdAt: '09:00',
  },
];

export function ChatPage() {
  const { user } = useAuth();
  const { activePortfolio, selectedPortfolios, isAllPortfoliosSelected } = usePortfolios();
  const chatStorageKey = getScopedStorageKey(storageKeys.chat, user?.id);
  const [messages, setMessages] = useState<ChatMessage[]>(() => readStorage(chatStorageKey, initialGuide));
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    setMessages(readStorage(chatStorageKey, initialGuide));
  }, [chatStorageKey]);

  useEffect(() => {
    writeStorage(chatStorageKey, messages);
  }, [chatStorageKey, messages]);

  async function send(content: string) {
    if (!content.trim() || sending) return;

    const createdAt = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      createdAt,
    };
    const outgoing = [...messages, userMsg];
    setMessages(outgoing);
    setText('');
    setSending(true);

    try {
      const response = await api.post<ChatApiResponse>('/chat', {
        messages: outgoing.map((message) => ({
          role: message.role,
          content: message.content,
        })),
        portfolio_id: isAllPortfoliosSelected ? null : activePortfolio?.id ?? null,
        use_all_portfolios: isAllPortfoliosSelected,
      });
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.message,
          createdAt,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: 'Nao consegui gerar a resposta agora. Tente novamente em alguns instantes.',
          createdAt,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(text);
  }

  const lastCount = useMemo(() => messages.length, [messages.length]);

  return (
    <div className="space-y-4">
      <section className="rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(225,94,242,0.08)_0%,rgba(255,255,255,0.96)_65%,rgba(61,77,156,0.08)_100%)] p-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-[var(--accent-soft)] px-4 py-2 text-sm font-semibold">
              <BookOpenText size={16} />
              Guia rapido de investimentos
            </div>
            <h2 className="mt-4 text-3xl font-bold">Perguntas frequentes com linguagem simples</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Use este guia para revisar conceitos do mercado e pedir um resumo basico da carteira ativa.
            </p>
            <p className="mt-3 text-sm font-semibold text-[var(--brand)]">
              Contexto atual: {getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected)}
            </p>
          </div>
          <div className="rounded-[24px] bg-white p-4 text-sm text-[var(--text-muted)]">
            <p className="font-semibold text-[var(--text-main)]">{lastCount} mensagens no historico</p>
            <p className="mt-1">
              {isAllPortfoliosSelected
                ? `Leitura baseada em ${selectedPortfolios.length} carteiras.`
                : activePortfolio
                  ? `Leitura contextual baseada em ${getPortfolioLabel(activePortfolio)}.`
                  : 'Use as sugestoes abaixo para comecar mais rapido.'}
            </p>
          </div>
        </div>
      </section>

      <Card title="Guia do Operum">
        <div className="max-h-[60vh] space-y-3 overflow-y-auto rounded-[24px] bg-[var(--bg-surface-strong)] p-4">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`max-w-[88%] rounded-[20px] px-4 py-3 text-sm leading-6 ${
                m.role === 'assistant' ? 'bg-white text-[var(--text-main)]' : 'ml-auto bg-[var(--brand)] text-white'
              }`}
            >
              <p>{m.content}</p>
              <p className="mt-1 text-[11px] opacity-70">{m.createdAt}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => void send(s)}
              className="rounded-full bg-[var(--accent-soft)] px-3 py-2 text-xs font-semibold text-[var(--text-main)] hover:bg-[var(--complementary-soft)]"
            >
              {s}
            </button>
          ))}
        </div>
        <form onSubmit={onSubmit} className="mt-4 flex gap-2">
          <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Digite sua duvida" />
          <Button type="submit" disabled={sending}>
            {sending ? 'Enviando...' : 'Enviar'}
          </Button>
        </form>
      </Card>
    </div>
  );
}
