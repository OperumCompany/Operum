import {
  AlertCircle, ArrowRight, BriefcaseBusiness, ChartNoAxesColumnIncreasing,
  CircleDollarSign, Layers3, LoaderCircle, Sparkles, TrendingDown, TrendingUp, WalletCards,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { PortfolioOpinion } from '../components/PortfolioOpinion';
import { Card } from '../components/UI';
import { usePortfolios } from '../context/PortfoliosContext';
import { useNearViewport } from '../hooks/useNearViewport';
import type { NewsItem, PortfolioHistoryResponse, PortfolioPricesResponse } from '../types';
import {
  buildCurrencySummaries, consolidateHistoriesByCurrency,
  type DashboardCurrencySummary, type DashboardRankingItem,
} from '../utils/dashboardOverview';
import api from '../utils/api';
import { getActivePortfolioSelectionLabel, mapAssetClassToLabel } from '../utils/portfolios';

const PERIODS = [
  { value: '1m', label: '1 mês' },
  { value: '6m', label: '6 meses' },
  { value: '1y', label: '1 ano' },
  { value: 'max', label: 'Máximo' },
] as const;

const CLASS_COLORS: Record<string, string> = {
  BR_STOCK: '#684CF2', FII: '#DF50F2', US_STOCK: '#3D4D9C', BDR: '#A896FF', CRYPTO: '#941289',
};

function money(value: number | null, currency: string) {
  if (value == null) return 'Indisponível';
  try {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency, maximumFractionDigits: 2 }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}`;
  }
}

function percent(value: number | null) {
  if (value == null) return 'Indisponível';
  return `${value >= 0 ? '+' : ''}${value.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function SummaryCards({ summary }: { summary: DashboardCurrencySummary }) {
  const positive = summary.unrealizedPnl != null && summary.unrealizedPnl >= 0;
  const pnlTone = summary.unrealizedPnl == null
    ? 'text-[var(--text-muted)]'
    : positive ? 'text-[var(--success-text)]' : 'text-[var(--danger-text)]';
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(15rem,.8fr)]">
      <section className="relative overflow-hidden rounded-[28px] border border-[var(--border-soft)] bg-[linear-gradient(135deg,var(--bg-surface-strong)_20%,var(--complementary-soft)_100%)] p-6 shadow-[var(--shadow-card)] sm:p-7">
        <div className="absolute -right-12 -top-16 h-44 w-44 rounded-full bg-[var(--accent)]/10 blur-2xl" />
        <div className="relative">
          <div className="flex items-center justify-between gap-3">
            <p className="font-data text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Valor atual</p>
            <span className="rounded-full border border-[var(--border-soft)] bg-[var(--bg-surface)] px-3 py-1 font-data text-xs font-semibold text-[var(--text-muted)]">{summary.currency}</span>
          </div>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <p className="font-data text-4xl font-bold tracking-tight text-[var(--text-main)] sm:text-5xl">{money(summary.currentValue, summary.currency)}</p>
            {summary.unrealizedPnlPct != null && <span className={`mb-1 rounded-full px-3 py-1 text-sm font-bold ${positive ? 'bg-[var(--success-soft)] text-[var(--success-text)]' : 'bg-[var(--danger-soft)] text-[var(--danger-text)]'}`}>{percent(summary.unrealizedPnlPct)}</span>}
          </div>
          <div className="mt-7 grid gap-4 border-t border-[var(--border-soft)] pt-5 sm:grid-cols-2">
            <div><p className="text-xs text-[var(--text-muted)]">Total investido</p><p className="mt-1 font-data text-lg font-bold">{money(summary.investedValue, summary.currency)}</p></div>
            <div><p className="text-xs text-[var(--text-muted)]">P&amp;L não realizado</p><p className={`mt-1 font-data text-lg font-bold ${pnlTone}`}>{money(summary.unrealizedPnl, summary.currency)}</p></div>
          </div>
        </div>
      </section>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-1">
        <Card className="min-w-0"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--accent-soft)] text-[var(--brand)]"><WalletCards size={19} /></span><p className="mt-4 text-sm text-[var(--text-muted)]">Ativos acompanhados</p><p className="mt-1 font-data text-3xl font-bold">{summary.positionCount}</p></Card>
        <Card className="min-w-0"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--complementary-soft)] text-[var(--complementary)]"><Layers3 size={19} /></span><p className="mt-4 text-sm text-[var(--text-muted)]">Classes de ativos</p><p className="mt-1 font-data text-3xl font-bold">{summary.classCount}</p></Card>
      </div>
    </div>
  );
}

function DashboardEvolution({ groups, loading, period, onPeriodChange }: {
  groups: ReturnType<typeof consolidateHistoriesByCurrency>;
  loading: boolean;
  period: PortfolioHistoryResponse['period'];
  onPeriodChange: (period: PortfolioHistoryResponse['period']) => void;
}) {
  return (
    <Card title="Evolução do patrimônio" right={<TrendingUp size={18} className="text-[var(--brand)]" />}>
      <div className="mb-5 flex gap-2 overflow-x-auto pb-1" aria-label="Período da evolução">
        {PERIODS.map((option) => <button key={option.value} type="button" onClick={() => onPeriodChange(option.value)} aria-pressed={period === option.value} className={`min-h-10 shrink-0 rounded-full px-4 text-xs font-semibold transition ${period === option.value ? 'bg-[#684cf2] text-white shadow-sm' : 'border border-[var(--border-soft)] bg-[var(--bg-surface-muted)] text-[var(--text-main)] hover:border-[var(--brand)]'}`}>{option.label}</button>)}
      </div>
      {loading && <div className="flex h-72 items-center justify-center gap-2 text-sm text-[var(--text-muted)]"><LoaderCircle size={18} className="animate-spin" />Carregando evolução...</div>}
      {!loading && !groups.some((group) => group.points.length) && <div className="flex h-64 items-center justify-center text-center text-sm text-[var(--text-muted)]">O histórico aparecerá após a inclusão de ativos.</div>}
      {!loading && groups.map((group) => group.points.length > 0 && (
        <section key={group.currency} className="mb-6 last:mb-0">
          {groups.length > 1 && <p className="mb-3 font-data text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Moeda-base {group.currency}</p>}
          <div className="h-[300px] w-full sm:h-[340px]" role="img" aria-label={`Evolução do valor de mercado e do total investido em ${group.currency}`}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={group.points.map((point) => ({ ...point, label: new Date(`${point.date}T00:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }) }))} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs><linearGradient id={`dashboard-area-${group.currency.replace(/\W/g, '')}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#684CF2" stopOpacity={0.3} /><stop offset="100%" stopColor="#684CF2" stopOpacity={0.02} /></linearGradient></defs>
                <CartesianGrid stroke="var(--border-soft)" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={30} />
                <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={(value) => new Intl.NumberFormat('pt-BR', { notation: 'compact' }).format(Number(value))} />
                <Legend />
                <Tooltip content={({ active, payload }) => {
                  const point = payload?.[0]?.payload as { date: string; marketValue: number | null; investedValue: number | null } | undefined;
                  if (!active || !point) return null;
                  return <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3 text-xs shadow-[var(--shadow-float)]"><p className="font-semibold">{new Date(`${point.date}T00:00:00`).toLocaleDateString('pt-BR')}</p><p className="mt-2 text-[var(--brand)]">Valor: {money(point.marketValue, group.currency)}</p><p className="mt-1 text-[var(--accent)]">Investido: {money(point.investedValue, group.currency)}</p></div>;
                }} />
                <Area type="monotone" dataKey="marketValue" name="Valor de mercado" stroke="#684CF2" strokeWidth={3} fill={`url(#dashboard-area-${group.currency.replace(/\W/g, '')})`} connectNulls isAnimationActive={false} />
                <Line type="monotone" dataKey="investedValue" name="Total investido" stroke="#DF50F2" strokeWidth={2} strokeDasharray="7 5" dot={false} connectNulls isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="sr-only">Último valor disponível: {money(group.points[group.points.length - 1]?.marketValue ?? null, group.currency)}; total investido: {money(group.points[group.points.length - 1]?.investedValue ?? null, group.currency)}.</p>
        </section>
      ))}
    </Card>
  );
}

function AllocationChart({ summary }: { summary: DashboardCurrencySummary }) {
  const data = summary.allocation.map((item) => ({ ...item, label: mapAssetClassToLabel(item.assetClass) }));
  return (
    <Card title="Alocação por classe" right={<ChartNoAxesColumnIncreasing size={18} className="text-[var(--brand)]" />}>
      <p className="mb-4 text-sm text-[var(--text-muted)]">Participação calculada pelo valor financeiro atual.</p>
      {!data.length ? <div className="flex h-56 items-center justify-center text-sm text-[var(--text-muted)]">Sem cotações para calcular a alocação.</div> : <><div className="h-[280px] w-full" role="img" aria-label={`Alocação financeira por classe em ${summary.currency}`}><ResponsiveContainer width="100%" height="100%"><BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 12, bottom: 4 }}><CartesianGrid stroke="var(--border-soft)" strokeDasharray="4 4" horizontal={false} /><XAxis type="number" domain={[0, 100]} tickFormatter={(value) => `${value}%`} tickLine={false} axisLine={false} /><YAxis type="category" dataKey="label" width={112} tickLine={false} axisLine={false} /><Tooltip cursor={{ fill: 'var(--bg-surface-muted)' }} formatter={(_, __, item) => { const payload = item.payload as { value: number; percent: number }; return [`${payload.percent.toFixed(1)}% · ${money(payload.value, summary.currency)}`, 'Participação']; }} /><Bar dataKey="percent" radius={[0, 10, 10, 0]} maxBarSize={32} isAnimationActive={false}>{data.map((item) => <Cell key={item.assetClass} fill={CLASS_COLORS[item.assetClass] ?? '#8B7CF6'} />)}</Bar></BarChart></ResponsiveContainer></div><ul className="mt-3 flex flex-wrap gap-2" aria-label="Resumo textual da alocação">{data.map((item) => <li key={`legend-${item.assetClass}`} className="rounded-full bg-[var(--bg-surface-muted)] px-3 py-1.5 text-xs text-[var(--text-muted)]"><span className="font-semibold text-[var(--text-main)]">{item.label}</span> {item.percent.toFixed(1)}%</li>)}</ul></>}
    </Card>
  );
}

function RankingRow({ item, currency }: { item: DashboardRankingItem; currency: string }) {
  const positive = item.pnl >= 0;
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-muted)] p-3">
      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${positive ? 'bg-[var(--success-soft)] text-[var(--success-text)]' : 'bg-[var(--danger-soft)] text-[var(--danger-text)]'}`}>{positive ? <TrendingUp size={17} /> : <TrendingDown size={17} />}</span>
      <div className="min-w-0 flex-1"><p className="font-data text-sm font-bold">{item.ticker}</p><p className="truncate text-xs text-[var(--text-muted)]">{mapAssetClassToLabel(item.assetClass)} · {item.percent.toFixed(1)}% da carteira</p></div>
      <div className="shrink-0 text-right"><p className={`font-data text-sm font-bold ${positive ? 'text-[var(--success-text)]' : 'text-[var(--danger-text)]'}`}>{percent(item.pnlPct)}</p><p className="text-xs text-[var(--text-muted)]">{money(item.value, currency)}</p></div>
    </div>
  );
}

function PerformanceRanking({ summary }: { summary: DashboardCurrencySummary }) {
  const best = summary.ranking.slice(0, 3);
  const bestTickers = new Set(best.map((item) => item.ticker));
  const worst = [...summary.ranking].sort((a, b) => a.pnlPct - b.pnlPct).filter((item) => !bestTickers.has(item.ticker)).slice(0, 3);
  return (
    <Card title="Desempenho dos ativos" right={<CircleDollarSign size={18} className="text-[var(--brand)]" />}>
      {!best.length ? <div className="flex h-56 items-center justify-center text-center text-sm text-[var(--text-muted)]">Adicione preço médio e aguarde as cotações para comparar resultados.</div> : <div className="grid gap-5 sm:grid-cols-2"><section><p className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--success-text)]">Maiores resultados</p><div className="space-y-2">{best.map((item) => <RankingRow key={`best-${item.assetClass}-${item.ticker}`} item={item} currency={summary.currency} />)}</div></section><section><p className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--danger-text)]">Pontos de atenção</p>{worst.length ? <div className="space-y-2">{worst.map((item) => <RankingRow key={`worst-${item.assetClass}-${item.ticker}`} item={item} currency={summary.currency} />)}</div> : <p className="rounded-2xl bg-[var(--bg-surface-muted)] p-4 text-sm text-[var(--text-muted)]">Mais ativos com dados completos são necessários para comparar os extremos.</p>}</section></div>}
    </Card>
  );
}

export function DashboardPage() {
  const { activePortfolio, selectedPortfolios, isAllPortfoliosSelected, loading: portfoliosLoading } = usePortfolios();
  const priceSelectionKey = selectedPortfolios.map((portfolio) => (
    `${portfolio.id}:${portfolio.positions.map((position) => `${position.ticker}:${position.quantity}:${position.avg_price ?? ''}`).join(',')}`
  )).join('|');
  const defaultPeriod: PortfolioHistoryResponse['period'] = !isAllPortfoliosSelected && activePortfolio?.kind === 'example' ? '1y' : '6m';
  const [period, setPeriod] = useState<PortfolioHistoryResponse['period']>(defaultPeriod);
  const [prices, setPrices] = useState<Map<string, PortfolioPricesResponse>>(new Map());
  const [histories, setHistories] = useState<Map<string, PortfolioHistoryResponse>>(new Map());
  const [pricesLoading, setPricesLoading] = useState(false);
  const [settledPriceSelectionKey, setSettledPriceSelectionKey] = useState('');
  const [historyLoading, setHistoryLoading] = useState(false);
  const [priceWarning, setPriceWarning] = useState('');
  const [historyWarning, setHistoryWarning] = useState('');
  const [relatedNews, setRelatedNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const historySection = useNearViewport();
  const secondarySection = useNearViewport();

  useEffect(() => { setPeriod(defaultPeriod); }, [activePortfolio?.id, defaultPeriod, isAllPortfoliosSelected]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedPortfolios.length) { setPrices(new Map()); setPricesLoading(false); setPriceWarning(''); setSettledPriceSelectionKey(''); return; }
    setPricesLoading(true); setPriceWarning('');
    Promise.allSettled(selectedPortfolios.map(async (portfolio) => ({ id: portfolio.id, data: await api.get<PortfolioPricesResponse>(`/portfolios/${portfolio.id}/prices?include_sparkline=false`) })))
      .then((results) => {
        if (cancelled) return;
        const next = new Map<string, PortfolioPricesResponse>(); let failures = 0;
        for (const result of results) result.status === 'fulfilled' ? next.set(result.value.id, result.value.data) : failures += 1;
        setPrices(next); setPriceWarning(failures ? `Não foi possível atualizar os preços de ${failures} carteira(s).` : '');
      }).finally(() => {
        if (!cancelled) {
          setPricesLoading(false);
          setSettledPriceSelectionKey(priceSelectionKey);
        }
      });
    return () => { cancelled = true; };
  }, [priceSelectionKey, selectedPortfolios]);

  const primaryDataReady = !portfoliosLoading
    && (!selectedPortfolios.length || settledPriceSelectionKey === priceSelectionKey);
  const historyReady = primaryDataReady && historySection.isNearViewport;
  const secondaryReady = primaryDataReady && secondarySection.isNearViewport;

  useEffect(() => {
    let cancelled = false;
    if (!historyReady || !selectedPortfolios.length) { setHistories(new Map()); setHistoryLoading(false); setHistoryWarning(''); return; }
    setHistoryLoading(true); setHistoryWarning('');
    Promise.allSettled(selectedPortfolios.map(async (portfolio) => ({ id: portfolio.id, data: await api.get<PortfolioHistoryResponse>(`/portfolios/${portfolio.id}/history?period=${period}`) })))
      .then((results) => {
        if (cancelled) return;
        const next = new Map<string, PortfolioHistoryResponse>(); let failures = 0;
        for (const result of results) result.status === 'fulfilled' ? next.set(result.value.id, result.value.data) : failures += 1;
        setHistories(next); setHistoryWarning(failures ? `Não foi possível carregar o histórico de ${failures} carteira(s).` : '');
      }).finally(() => { if (!cancelled) setHistoryLoading(false); });
    return () => { cancelled = true; };
  }, [historyReady, period, selectedPortfolios]);

  useEffect(() => {
    let cancelled = false;
    if (!secondaryReady) {
      setRelatedNews([]);
      setNewsLoading(false);
      return;
    }
    const route = activePortfolio && !isAllPortfoliosSelected ? `/portfolios/${activePortfolio.id}/news` : '/news?page=1&page_size=3';
    setRelatedNews([]);
    setNewsLoading(true);
    api.get<{ items: NewsItem[] }>(route)
      .then((data) => { if (!cancelled) setRelatedNews(data.items.slice(0, 3)); })
      .catch(() => { if (!cancelled) setRelatedNews([]); })
      .finally(() => { if (!cancelled) setNewsLoading(false); });
    return () => { cancelled = true; };
  }, [activePortfolio, isAllPortfoliosSelected, secondaryReady]);

  const summaries = useMemo(() => buildCurrencySummaries(selectedPortfolios, prices), [prices, selectedPortfolios]);
  const historyGroups = useMemo(() => consolidateHistoriesByCurrency(selectedPortfolios, histories), [histories, selectedPortfolios]);
  const selectionLabel = getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected);
  const noPositions = !selectedPortfolios.some((portfolio) => portfolio.positions.length > 0);
  const aiPortfolioId = !isAllPortfoliosSelected ? activePortfolio?.id : undefined;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div><p className="eyebrow">Visão geral</p><h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Seu patrimônio em perspectiva.</h1><p className="mt-2 text-sm text-[var(--text-muted)]">Acompanhando: <span className="font-semibold text-[var(--text-main)]">{selectionLabel}</span></p></div>
        <Link to="/app/carteiras" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[var(--border-soft)] px-4 py-2.5 text-sm font-semibold transition hover:border-[var(--border-strong)] hover:bg-[var(--bg-surface-muted)]"><BriefcaseBusiness size={17} />Carteiras</Link>
      </header>

      {(portfoliosLoading || pricesLoading) && !summaries.length && <div className="flex min-h-64 items-center justify-center gap-2 rounded-[28px] border border-[var(--border-soft)] bg-[var(--bg-surface)] text-sm text-[var(--text-muted)]"><LoaderCircle size={19} className="animate-spin" />Atualizando sua visão geral...</div>}
      {!portfoliosLoading && !selectedPortfolios.length && <Card className="py-12 text-center"><WalletCards size={32} className="mx-auto text-[var(--brand)]" /><h2 className="mt-4 text-xl font-bold">Crie sua primeira carteira</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-muted)]">Adicione uma carteira para acompanhar valores, evolução e alocação em um só lugar.</p><Link to="/app/carteiras" className="mt-5 inline-flex min-h-11 items-center justify-center rounded-lg bg-[#684cf2] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(104,76,242,0.18)] transition hover:bg-[#4f2cd9]">Ir para Carteiras</Link></Card>}
      {!!selectedPortfolios.length && noPositions && !pricesLoading && <Card className="py-12 text-center"><Layers3 size={32} className="mx-auto text-[var(--brand)]" /><h2 className="mt-4 text-xl font-bold">Sua visão geral começa com os ativos</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-[var(--text-muted)]">A carteira selecionada ainda está vazia. Inclua seus investimentos para liberar os indicadores e gráficos.</p><Link to={activePortfolio ? `/app/carteiras/${activePortfolio.id}` : '/app/carteiras'} className="mt-5 inline-flex min-h-11 items-center justify-center rounded-lg bg-[#684cf2] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(104,76,242,0.18)] transition hover:bg-[#4f2cd9]">Adicionar ativos</Link></Card>}
      {!noPositions && !pricesLoading && !summaries.length && <Card className="py-10 text-center"><AlertCircle size={30} className="mx-auto text-[var(--danger-text)]" /><h2 className="mt-4 text-xl font-bold">Dados financeiros indisponíveis</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-[var(--text-muted)]">Não foi possível calcular valores sem uma resposta de preços. Seus ativos permanecem preservados; tente atualizar a página em instantes.</p></Card>}

      {!noPositions && summaries.map((summary) => <section key={summary.currency} className="space-y-5">
        {summaries.length > 1 && <div className="flex items-center gap-3"><span className="h-px flex-1 bg-[var(--border-soft)]" /><h2 className="font-data text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Consolidado em {summary.currency}</h2><span className="h-px flex-1 bg-[var(--border-soft)]" /></div>}
        <SummaryCards summary={summary} />
        {(summary.missingQuotes > 0 || summary.missingCosts > 0) && <div className="flex items-start gap-3 rounded-2xl border border-[var(--border-strong)] bg-[var(--accent-soft)] p-4 text-sm text-[var(--text-muted)]"><AlertCircle size={18} className="mt-0.5 shrink-0 text-[var(--accent-strong)]" /><p>{summary.missingQuotes > 0 && `${summary.missingQuotes} ativo(s) sem cotação não entram no valor atual. `}{summary.missingCosts > 0 && `${summary.missingCosts} ativo(s) sem preço médio não entram no custo e no P&L.`}</p></div>}
        <div className="grid gap-5 xl:grid-cols-[1.08fr_.92fr]"><AllocationChart summary={summary} /><PerformanceRanking summary={summary} /></div>
      </section>)}

      {!noPositions && <div ref={primaryDataReady ? historySection.ref : undefined} className="min-h-[360px]">
        {historyReady
          ? <DashboardEvolution groups={historyGroups} loading={historyLoading} period={period} onPeriodChange={setPeriod} />
          : <Card title="Evolução do patrimônio"><div role="status" className="h-72 rounded-2xl bg-[var(--bg-surface-muted)] motion-safe:animate-pulse"><span className="sr-only">A evolução será carregada ao se aproximar desta seção.</span></div></Card>}
      </div>}
      {(priceWarning || historyWarning) && <div className="space-y-2">{[priceWarning, historyWarning].filter(Boolean).map((warning) => <p key={warning} className="flex items-start gap-2 rounded-xl bg-[var(--danger-soft)] p-3 text-sm text-[var(--danger-text)]"><AlertCircle size={16} className="mt-0.5 shrink-0" />{warning}</p>)}</div>}

      <div ref={primaryDataReady ? secondarySection.ref : undefined} className="grid min-h-[360px] gap-5 xl:grid-cols-[1fr_1fr]">
        {secondaryReady ? <>
          <section id="dashboard-ai" className="scroll-mt-24">{aiPortfolioId ? <PortfolioOpinion portfolioId={aiPortfolioId} /> : <Card title="Análise da carteira"><Sparkles size={22} className="text-[var(--brand)]" /><p className="mt-4 text-sm leading-6 text-[var(--text-muted)]">Selecione uma carteira específica no cabeçalho para visualizar a análise por IA. O consolidado não mistura análises de carteiras diferentes.</p></Card>}</section>
          <Card title="Notícias para acompanhar" right={<Link to="/app/noticias" className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand)]">Ver todas <ArrowRight size={15} /></Link>}><div className="space-y-3">{newsLoading ? <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-[var(--text-muted)]"><LoaderCircle size={18} className="animate-spin" />Carregando notícias...</div> : relatedNews.length ? relatedNews.map((item) => <article key={item.id} className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-muted)] p-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--brand)]">{item.source_name}</p><h3 className="mt-2 font-semibold leading-6">{item.title}</h3><p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--text-muted)]">{item.summary}</p></article>) : <p className="py-8 text-center text-sm text-[var(--text-muted)]">Sem notícias relevantes para a seleção atual.</p>}</div></Card>
        </> : <><Card><div role="status" className="h-64 rounded-2xl bg-[var(--bg-surface-muted)] motion-safe:animate-pulse"><span className="sr-only">A análise será carregada ao se aproximar desta seção.</span></div></Card><Card><div role="status" className="h-64 rounded-2xl bg-[var(--bg-surface-muted)] motion-safe:animate-pulse"><span className="sr-only">As notícias serão carregadas ao se aproximar desta seção.</span></div></Card></>}
      </div>
    </div>
  );
}
