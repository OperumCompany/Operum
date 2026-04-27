import { FormEvent, useEffect, useMemo, useState } from 'react';
import { MessageSquareHeart } from 'lucide-react';
import { Button, Card, Input } from '../components/UI';
import { useAuth } from '../context/AuthContext';
import { usePortfolios } from '../context/PortfoliosContext';
import { assetsCatalog, initialChat } from '../data/mocks';
import { ChatMessage } from '../types';
import { getScopedStorageKey, readStorage, storageKeys, writeStorage } from '../utils/storage';
import { getActivePortfolioSelectionLabel, getPortfolioLabel } from '../utils/portfolios';

const suggestions = ['O que é renda fixa?', 'O que é inflação?', 'O que significa liquidez?', 'Como está a carteira ativa?'];

function getPortfolioSummary(
  activePortfolio: ReturnType<typeof usePortfolios>['activePortfolio'],
  selectedPortfolios: ReturnType<typeof usePortfolios>['selectedPortfolios'],
  isAllPortfoliosSelected: boolean,
) {
  const selectedAssets = selectedPortfolios.flatMap((portfolio) => portfolio.assets);
  if (!selectedAssets.length) {
    return 'A carteira ativa ainda não possui ativos suficientes para uma leitura personalizada.';
  }

  const topAsset = [...selectedAssets].sort((a, b) => b.allocation - a.allocation)[0];
  const assetName = assetsCatalog.find((item) => item.ticker === topAsset.ticker)?.name ?? topAsset.ticker;
  if (isAllPortfoliosSelected) {
    return `No consolidado de todas as carteiras, o maior peso hoje está em ${assetName} com ${topAsset.allocation}% da alocação.`;
  }
  return activePortfolio
    ? `Na carteira ativa ${getPortfolioLabel(activePortfolio)}, o maior peso hoje está em ${assetName} com ${topAsset.allocation}% da alocação.`
    : 'Nenhuma carteira foi selecionada para análise.';
}

function answer(
  text: string,
  activePortfolio: ReturnType<typeof usePortfolios>['activePortfolio'],
  selectedPortfolios: ReturnType<typeof usePortfolios>['selectedPortfolios'],
  isAllPortfoliosSelected: boolean,
): string {
  const normalized = text.toLowerCase();
  if (normalized.includes('carteira ativa') || normalized.includes('como está')) {
    return getPortfolioSummary(activePortfolio, selectedPortfolios, isAllPortfoliosSelected);
  }
  if (normalized.includes('renda fixa')) {
    return 'Renda fixa reúne investimentos com regras de rendimento mais previsíveis, como CDB e Tesouro. O risco e a liquidez mudam conforme o emissor e o prazo.';
  }
  if (normalized.includes('inflação')) {
    return 'Inflação é a alta geral de preços. Quando sobe, o dinheiro compra menos coisas e isso influencia juros e investimentos.';
  }
  if (normalized.includes('liquidez')) {
    return 'Liquidez é a facilidade de transformar um ativo em dinheiro sem perder valor de forma relevante.';
  }
  if (normalized.includes('cdb') || normalized.includes('tesouro')) {
    return 'CDB é emitido por banco e pode ter cobertura do FGC dentro dos limites. Tesouro é título público e costuma ser visto como opção de risco mais baixo.';
  }
  return activePortfolio || isAllPortfoliosSelected
    ? `Posso ajudar com conceitos de mercado e também comentar ${isAllPortfoliosSelected ? 'o consolidado de todas as carteiras' : `a carteira ativa ${getPortfolioLabel(activePortfolio!)}`} com linguagem simples.`
    : 'Posso ajudar com conceitos de mercado, risco, diversificação, inflação, juros e classes de ativos com linguagem simples.';
}

export function ChatPage() {
  const { user } = useAuth();
  const { activePortfolio, selectedPortfolios, isAllPortfoliosSelected } = usePortfolios();
  const chatStorageKey = getScopedStorageKey(storageKeys.chat, user?.id);
  const [messages, setMessages] = useState<ChatMessage[]>(() => readStorage(chatStorageKey, initialChat));
  const [text, setText] = useState('');

  useEffect(() => {
    setMessages(readStorage(chatStorageKey, initialChat));
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
      content: answer(content, activePortfolio, selectedPortfolios, isAllPortfoliosSelected),
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
              <MessageSquareHeart size={16} />
              Tire dúvidas sem medo de perguntar
            </div>
            <h2 className="mt-4 text-3xl font-bold">Chat com linguagem simples</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Pergunte o que quiser sobre termos financeiros, tipos de investimento e comportamento do mercado.
            </p>
            <p className="mt-3 text-sm font-semibold text-[var(--brand)]">
              Analisando agora: {getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected)}
            </p>
          </div>
          <div className="rounded-[24px] bg-white p-4 text-sm text-[var(--text-muted)]">
            <p className="font-semibold text-[var(--text-main)]">{lastCount} mensagens no histórico</p>
            <p className="mt-1">
              {isAllPortfoliosSelected
                ? `Leitura baseada em ${selectedPortfolios.length} carteiras.`
                : 'Use as sugestões abaixo para começar mais rápido.'}
            </p>
          </div>
        </div>
      </section>

      <Card title="Conversa com o Operum">
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
          <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Digite sua dúvida" />
          <Button type="submit">Enviar</Button>
        </form>
      </Card>
    </div>
  );
}
