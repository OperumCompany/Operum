import { FormEvent, useEffect, useMemo, useState } from 'react';
import { BookOpenText } from 'lucide-react';
import { Button, Card, Input } from '../components/UI';
import { useAuth } from '../context/AuthContext';
import { usePortfolios } from '../context/PortfoliosContext';
import { Asset, ChatMessage } from '../types';
import { getScopedStorageKey, readStorage, storageKeys, writeStorage } from '../utils/storage';
import { getActivePortfolioSelectionLabel, getPortfolioLabel } from '../utils/portfolios';
import api from '../utils/api';

const suggestions = ['O que e renda variavel?', 'O que e inflacao?', 'O que significa liquidez?', 'Como esta a carteira ativa?'];
const initialGuide: ChatMessage[] = [{
  id: 'guide-1',
  role: 'assistant',
  content: 'Este espaÃ§o funciona como um guia rÃ¡pido. VocÃª pode tirar dÃºvidas bÃ¡sicas de investimentos e pedir um resumo simples da carteira ativa.',
  createdAt: '09:00',
}];

function getPortfolioSummary(
  assets: Asset[],
  activePortfolio: ReturnType<typeof usePortfolios>['activePortfolio'],
  selectedPortfolios: ReturnType<typeof usePortfolios>['selectedPortfolios'],
  isAllPortfoliosSelected: boolean,
) {
  const selectedPositions = selectedPortfolios.flatMap((p) => p.positions);
  if (!selectedPositions.length) {
    return 'A carteira ativa ainda nÃ£o possui ativos suficientes para uma leitura personalizada.';
  }

  const topPos = [...selectedPositions].sort((a, b) => b.quantity - a.quantity)[0];
  const assetName = assets.find((item) => item.ticker === topPos.ticker)?.name ?? topPos.ticker;
  if (isAllPortfoliosSelected) {
    return `No consolidado de todas as carteiras, o maior peso hoje estÃ¡ em ${assetName} com ${topPos.quantity} unidades.`;
  }
  return activePortfolio
    ? `Na carteira ativa ${getPortfolioLabel(activePortfolio)}, o maior peso hoje estÃ¡ em ${assetName} com ${topPos.quantity} unidades.`
    : 'Nenhuma carteira foi selecionada para anÃ¡lise.';
}

function answer(
  assets: Asset[],
  text: string,
  activePortfolio: ReturnType<typeof usePortfolios>['activePortfolio'],
  selectedPortfolios: ReturnType<typeof usePortfolios>['selectedPortfolios'],
  isAllPortfoliosSelected: boolean,
): string {
  const normalized = text.toLowerCase();
  if (normalized.includes('carteira ativa') || normalized.includes('como estÃ¡')) {
    return getPortfolioSummary(assets, activePortfolio, selectedPortfolios, isAllPortfoliosSelected);
  }
  if (normalized.includes('renda variavel') || normalized.includes('renda variavel')) {
    return 'Renda variavel reune ativos como acoes, FIIs, BDRs, ETFs e cripto. O retorno oscila com preco de mercado, resultados, juros, liquidez e expectativas.';
  }
  if (normalized.includes('inflaÃ§Ã£o')) {
    return 'InflaÃ§Ã£o Ã© a alta geral de preÃ§os. Quando sobe, o dinheiro compra menos coisas e isso influencia juros e investimentos.';
  }
  if (normalized.includes('liquidez')) {
    return 'Liquidez Ã© a facilidade de transformar um ativo em dinheiro sem perder valor de forma relevante.';
  }
  if (normalized.includes('acao') || normalized.includes('acoes') || normalized.includes('fii') || normalized.includes('bdr')) {
    return 'Para renda variavel, observe liquidez, setor, concentracao, historico de precos, noticias relevantes e como o ativo se encaixa na carteira.';
  }
  return activePortfolio || isAllPortfoliosSelected
    ? `Posso ajudar com conceitos de mercado e tambÃ©m comentar ${isAllPortfoliosSelected ? 'o consolidado de todas as carteiras' : `a carteira ativa ${getPortfolioLabel(activePortfolio!)}`} com linguagem simples.`
    : 'Posso ajudar com conceitos de mercado, risco, diversificaÃ§Ã£o, inflaÃ§Ã£o, juros e classes de ativos com linguagem simples.';
}

export function ChatPage() {
  const { user } = useAuth();
  const { activePortfolio, selectedPortfolios, isAllPortfoliosSelected } = usePortfolios();
  const chatStorageKey = getScopedStorageKey(storageKeys.chat, user?.id);
  const [messages, setMessages] = useState<ChatMessage[]>(() => readStorage(chatStorageKey, initialGuide));
  const [text, setText] = useState('');
  const [assets, setAssets] = useState<Asset[]>([]);

  useEffect(() => {
    api.get<Asset[]>('/assets/universe').then(setAssets).catch(() => setAssets([]));
  }, []);

  useEffect(() => {
    setMessages(readStorage(chatStorageKey, initialGuide));
  }, [chatStorageKey]);

  useEffect(() => {
    writeStorage(chatStorageKey, messages);
  }, [chatStorageKey, messages]);

  function send(content: string) {
    if (!content.trim()) return;
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      createdAt: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
    };
    const botMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: answer(assets, content, activePortfolio, selectedPortfolios, isAllPortfoliosSelected),
      createdAt: userMsg.createdAt,
    };
    setMessages((prev) => [...prev, userMsg, botMsg]);
    setText('');
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(text);
  }

  const lastCount = useMemo(() => messages.length, [messages.length]);

  return (
    <div className="space-y-4">
      <section className="rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(225,94,242,0.08)_0%,rgba(255,255,255,0.96)_65%,rgba(61,77,156,0.08)_100%)] p-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-[var(--accent-soft)] px-4 py-2 text-sm font-semibold">
              <BookOpenText size={16} />
              Guia rÃ¡pido de investimentos
            </div>
            <h2 className="mt-4 text-3xl font-bold">Perguntas frequentes com linguagem simples</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Use este guia para revisar conceitos do mercado e pedir um resumo bÃ¡sico da carteira ativa.
            </p>
            <p className="mt-3 text-sm font-semibold text-[var(--brand)]">
              Contexto atual: {getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected)}
            </p>
          </div>
          <div className="rounded-[24px] bg-white p-4 text-sm text-[var(--text-muted)]">
            <p className="font-semibold text-[var(--text-main)]">{lastCount} mensagens no histÃ³rico</p>
            <p className="mt-1">
              {isAllPortfoliosSelected
                ? `Leitura baseada em ${selectedPortfolios.length} carteiras.`
                : 'Use as sugestÃµes abaixo para comeÃ§ar mais rÃ¡pido.'}
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
              onClick={() => send(s)}
              className="rounded-full bg-[var(--accent-soft)] px-3 py-2 text-xs font-semibold text-[var(--text-main)] hover:bg-[var(--complementary-soft)]"
            >
              {s}
            </button>
          ))}
        </div>
        <form onSubmit={onSubmit} className="mt-4 flex gap-2">
          <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Digite sua dÃºvida" />
          <Button type="submit">Enviar</Button>
        </form>
      </Card>
    </div>
  );
}

