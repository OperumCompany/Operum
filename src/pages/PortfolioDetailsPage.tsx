import { FormEvent, Fragment, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Sparkles, ChevronDown, ChevronUp, ArrowDownUp } from 'lucide-react';
import {
  Area,
  CartesianGrid,
  Legend,
  Line,
  ComposedChart,
  ResponsiveContainer,
  ReferenceDot,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Button, Card, Input } from '../components/UI';
import { CompositionCharts } from '../components/CompositionCharts';
import { PortfolioAnalysisAI } from '../components/PortfolioAnalysisAI';
import { usePortfolios } from '../context/PortfoliosContext';
import { getPortfolioLabel } from '../utils/portfolios';
import api from '../utils/api';
import type { Asset, HorizonSeriesPoint, PortfolioAnalysis, PositionOpinion } from '../types';

type PriceRow = {
  ticker: string;
  asset_class: string;
  quantity: number;
  avg_price: number | null;
  current_price: number | null;
  currency: string;
  total_value: number | null;
  name: string;
  weight_pct: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
};

type PricesResponse = {
  portfolio_id: string;
  portfolio_name: string;
  total_value: number | null;
  total_unrealized_pnl: number | null;
  positions: PriceRow[];
};

const ASSET_CLASSES = ['BR_STOCK', 'FII', 'BDR', 'CRYPTO', 'US_STOCK', 'FIXED_INCOME'] as const;
const HISTORY_OPTIONS = [
  { key: '1w', label: '1 semana' },
  { key: '1m', label: '1 mes' },
  { key: '2m', label: '2 meses' },
  { key: '3m', label: '3 meses' },
] as const;
const OUTLOOK_OPTIONS = [
  { key: '1w', label: '1 semana' },
  { key: '1m', label: '1 mes' },
  { key: '2m', label: '2 meses' },
  { key: '3m', label: '3 meses' },
] as const;

const CLASS_LABELS: Record<string, string> = {
  BR_STOCK: 'Acoes Brasileiras',
  FII: 'Fundos Imobiliarios',
  BDR: 'BDRs',
  CRYPTO: 'Criptomoedas',
  US_STOCK: 'Acoes EUA',
  FIXED_INCOME: 'Renda Fixa',
};

type OpinionState = {
  data?: PositionOpinion;
  loading: boolean;
  error?: string;
  open: boolean;
  expandedSources?: Record<string, boolean>;
  historyHorizon: '1w' | '1m' | '2m' | '3m';
  outlookHorizon: '1w' | '1m' | '2m' | '3m';
};

type SortKey = 'ticker' | 'quantity' | 'current_price' | 'total_value' | 'weight_pct' | 'unrealized_pnl';
type HistoryHorizonKey = OpinionState['historyHorizon'];
type ChartPoint = {
  date: string;
  label: string;
  historico: number | null;
  perspectiva: number | null;
  areaHistorico: number | null;
  areaPerspectiva: number | null;
  precoAtual: number | null;
  isToday: boolean;
};

function resolveDisplayClass(assetClass: string, ticker: string, assets: Asset[]): string {
  if (assetClass === 'US_STOCK') {
    const asset = assets.find((a) => a.ticker === ticker);
    if (asset?.sub_type === 'BDR') return 'BDR';
  }
  return assetClass;
}

function confidenceLabel(confidence: string) {
  if (confidence === 'alta') return 'Confianca alta';
  if (confidence === 'media') return 'Confianca media';
  return 'Confianca baixa';
}

function fmtMoney(value: number | null | undefined, currency = 'BRL') {
  if (value == null) return '-';
  const prefix = currency === 'BRL' ? 'R$' : currency;
  return `${prefix} ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(value: number | null | undefined) {
  if (value == null) return '-';
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
}

function historyOptionLabel(horizon: HistoryHorizonKey) {
  return HISTORY_OPTIONS.find((option) => option.key === horizon)?.label ?? '3 meses';
}

function historySectionTitle(horizon: HistoryHorizonKey) {
  return horizon === '1w' ? 'Ultima semana' : `Ultimos ${historyOptionLabel(horizon)}`;
}

function horizonButtonClass(isActive: boolean) {
  return `rounded-full px-3 py-1.5 text-xs font-semibold transition ${
    isActive
      ? 'bg-[var(--accent-soft)] text-[var(--accent)] ring-1 ring-[var(--accent)]'
      : 'border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] text-[var(--text-main)] hover:border-[var(--accent)]'
  }`;
}

function formatChartDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
  });
}

function mergeChartSeries(
  historical: HorizonSeriesPoint[],
  forecast: HorizonSeriesPoint[],
  currentPrice: number | null | undefined,
): ChartPoint[] {
  const historicalMap = new Map(historical.map((point) => [point.date, point.value]));
  const forecastMap = new Map(forecast.map((point) => [point.date, point.value]));
  const dates = Array.from(new Set([...historicalMap.keys(), ...forecastMap.keys()])).sort();
  const todayDate = historical.length
    ? historical[historical.length - 1].date
    : forecast.length
      ? forecast[0].date
      : null;

  return dates.map((date) => ({
    date,
    label: formatChartDate(date),
    historico: historicalMap.has(date) ? (historicalMap.get(date) ?? null) : null,
    perspectiva: forecastMap.has(date) ? (forecastMap.get(date) ?? null) : null,
    areaHistorico: historicalMap.has(date) ? (historicalMap.get(date) ?? null) : null,
    areaPerspectiva: forecastMap.has(date) ? (forecastMap.get(date) ?? null) : null,
    precoAtual: date === todayDate ? currentPrice ?? historicalMap.get(date) ?? forecastMap.get(date) ?? null : null,
    isToday: date === todayDate,
  }));
}

export function PortfolioDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { portfolios, activePortfolioId, setActivePortfolioId, addPosition, removePosition, updatePortfolio } = usePortfolios();
  const [selectedClass, setSelectedClass] = useState<string>('');
  const [assetTicker, setAssetTicker] = useState('');
  const [quantity, setQuantity] = useState(10);
  const [avgPrice, setAvgPrice] = useState('');
  const [nameDraft, setNameDraft] = useState('');
  const [editingName, setEditingName] = useState(false);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [prices, setPrices] = useState<PricesResponse | null>(null);
  const [pricesLoading, setPricesLoading] = useState(false);
  const [positionOpinions, setPositionOpinions] = useState<Record<string, OpinionState>>({});
  const [tableQuery, setTableQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('weight_pct');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    api.get<Asset[]>('/assets/universe').then(setAssets).catch(() => {});
  }, []);

  const portfolio = portfolios.find((item) => item.id === id);

  useEffect(() => {
    if (!portfolio) return;
    setAnalysisLoading(true);
    setPricesLoading(true);
    setAnalysisError(null);
    Promise.all([
      api.get<PortfolioAnalysis>(`/portfolios/${portfolio.id}/analysis`),
      api.get<PricesResponse>(`/portfolios/${portfolio.id}/prices`),
    ])
      .then(([analysisData, pricesData]) => {
        setAnalysis(analysisData);
        setPrices(pricesData);
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : 'Erro ao carregar dados da carteira';
        setAnalysisError(msg);
        setAnalysis(null);
        setPrices(null);
      })
      .finally(() => {
        setAnalysisLoading(false);
        setPricesLoading(false);
      });
  }, [portfolio]);

  const filteredAssets = useMemo(() => {
    if (!selectedClass) return assets;
    if (selectedClass === 'BDR') {
      return assets.filter((a) => a.asset_class === 'US_STOCK' && a.sub_type === 'BDR');
    }
    return assets.filter((a) => a.asset_class === selectedClass);
  }, [assets, selectedClass]);

  const positionsByClass = useMemo(() => {
    if (!portfolio) return {};
    const query = tableQuery.trim().toLowerCase();
    const grouped: Record<string, typeof portfolio.positions> = {};
    for (const pos of portfolio.positions) {
      const asset = assets.find((item) => item.ticker === pos.ticker);
      const label = resolveDisplayClass(pos.asset_class, pos.ticker, assets);
      const haystack = `${pos.ticker} ${asset?.name ?? ''}`.toLowerCase();
      if (query && !haystack.includes(query)) continue;
      if (!grouped[label]) grouped[label] = [];
      grouped[label].push(pos);
    }

    const getComparable = (pos: typeof portfolio.positions[number]) => {
      const priceInfo = prices?.positions.find((item) => item.ticker === pos.ticker);
      switch (sortKey) {
        case 'ticker':
          return pos.ticker;
        case 'quantity':
          return pos.quantity;
        case 'current_price':
          return priceInfo?.current_price ?? Number.NEGATIVE_INFINITY;
        case 'total_value':
          return priceInfo?.total_value ?? Number.NEGATIVE_INFINITY;
        case 'unrealized_pnl':
          return priceInfo?.unrealized_pnl ?? Number.NEGATIVE_INFINITY;
        case 'weight_pct':
        default:
          return priceInfo?.weight_pct ?? Number.NEGATIVE_INFINITY;
      }
    };

    for (const key of Object.keys(grouped)) {
      grouped[key].sort((a, b) => {
        const left = getComparable(a);
        const right = getComparable(b);
        if (typeof left === 'string' && typeof right === 'string') {
          return sortDirection === 'asc' ? left.localeCompare(right) : right.localeCompare(left);
        }
        const diff = Number(left) - Number(right);
        return sortDirection === 'asc' ? diff : -diff;
      });
    }
    return grouped;
  }, [portfolio, assets, prices, sortDirection, sortKey, tableQuery]);

  const assetClassesWithPositions = useMemo(() => {
    return ASSET_CLASSES.filter((cls) => positionsByClass[cls]?.length);
  }, [positionsByClass]);

  function getPriceInfo(ticker: string) {
    return prices?.positions.find((p) => p.ticker === ticker);
  }

  async function addAsset(e: FormEvent) {
    e.preventDefault();
    if (!portfolio || !assetTicker) return;
    const asset = assets.find((a) => a.ticker === assetTicker);
    try {
      await addPosition(portfolio.id, {
        ticker: assetTicker,
        asset_class: asset?.asset_class ?? 'BR_STOCK',
        quantity: Math.max(0.01, quantity),
        avg_price: avgPrice ? parseFloat(avgPrice) : undefined,
      });
      setQuantity(10);
      setAvgPrice('');
      setAssetTicker('');
      setPositionOpinions({});
    } catch {
      // handled by context
    }
  }

  async function handleRemovePosition(ticker: string) {
    if (!portfolio) return;
    const confirmed = window.confirm(`Remover ${ticker} da carteira?`);
    if (!confirmed) return;
    try {
      await removePosition(portfolio.id, ticker);
      setPositionOpinions((prev) => {
        const next = { ...prev };
        delete next[ticker];
        return next;
      });
    } catch {
      // handled by context
    }
  }

  async function handleSaveName(e: FormEvent) {
    e.preventDefault();
    if (!portfolio || !nameDraft.trim()) return;
    try {
      await updatePortfolio(portfolio.id, { name: nameDraft.trim() });
      setNameDraft('');
      setEditingName(false);
    } catch {
      // handled by context
    }
  }

  async function loadPositionOpinion(
    ticker: string,
    options?: Partial<Pick<OpinionState, 'historyHorizon' | 'outlookHorizon'>> & { keepOpen?: boolean },
  ) {
    if (!portfolio) return;
    const existing = positionOpinions[ticker];
    const historyHorizon = options?.historyHorizon ?? existing?.historyHorizon ?? '3m';
    const outlookHorizon = options?.outlookHorizon ?? existing?.outlookHorizon ?? '3m';
    setPositionOpinions((prev) => ({
      ...prev,
      [ticker]: {
        ...existing,
        historyHorizon,
        outlookHorizon,
        loading: true,
        open: options?.keepOpen ?? true,
        error: undefined,
      },
    }));

    try {
      const data = await api.get<PositionOpinion>(
        `/models/opinion/${portfolio.id}/positions/${ticker}?history_horizon=${historyHorizon}&outlook_horizon=${outlookHorizon}`,
      );
      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: {
          loading: false,
          open: true,
          data,
          expandedSources: prev[ticker]?.expandedSources ?? {},
          historyHorizon,
          outlookHorizon,
        },
      }));
    } catch (e) {
      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: {
          ...prev[ticker],
          loading: false,
          open: true,
          error: e instanceof Error ? e.message : 'Erro ao gerar analise',
          historyHorizon,
          outlookHorizon,
        },
      }));
    }
  }

  async function togglePositionOpinion(ticker: string) {
    const existing = positionOpinions[ticker];
    if (existing?.open) {
      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: { ...existing, open: false },
      }));
      return;
    }
    await loadPositionOpinion(ticker);
  }

  function toggleSourceGroup(ticker: string, sourceName: string) {
    setPositionOpinions((prev) => {
      const current = prev[ticker];
      if (!current) return prev;
      const expandedSources = { ...(current.expandedSources ?? {}) };
      expandedSources[sourceName] = !expandedSources[sourceName];
      return {
        ...prev,
        [ticker]: {
          ...current,
          expandedSources,
        },
      };
    });
  }

  function updateSort(nextKey: SortKey) {
    if (sortKey === nextKey) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === 'ticker' ? 'asc' : 'desc');
  }

  if (!portfolio) {
    return (
      <Card title="Carteira nao encontrada">
        <p className="text-sm text-[var(--text-muted)]">A carteira solicitada nao existe ou foi removida.</p>
        <Button type="button" className="mt-4" onClick={() => navigate('/carteiras')}>
          Voltar para carteiras
        </Button>
      </Card>
    );
  }

  const isActive = activePortfolioId === portfolio.id;

  return (
    <div className="space-y-4">
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(225,94,242,0.08)_0%,rgba(255,255,255,0.96)_55%,rgba(61,77,156,0.08)_100%)] p-6 shadow-[var(--shadow-card)]">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">Carteira em detalhe</p>
          {editingName ? (
            <form onSubmit={handleSaveName} className="mt-2 flex items-center gap-2">
              <Input
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                className="text-2xl font-bold"
                placeholder={portfolio.name}
              />
              <Button type="submit">Salvar</Button>
              <Button type="button" variant="ghost" onClick={() => { setEditingName(false); setNameDraft(''); }}>
                Cancelar
              </Button>
            </form>
          ) : (
            <h2 className="mt-2 text-3xl font-bold">{getPortfolioLabel(portfolio)}</h2>
          )}
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            {portfolio.positions.length} ativo(s) â€¢ Moeda base: {portfolio.base_currency}
            {prices?.total_value != null && ` â€¢ Valor total: ${fmtMoney(prices.total_value)}`}
            {prices?.total_unrealized_pnl != null && ` â€¢ P&L nao realizado: ${fmtMoney(prices.total_unrealized_pnl)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!editingName && (
            <Button type="button" variant="ghost" onClick={() => { setEditingName(true); setNameDraft(portfolio.name); }}>
              Editar nome
            </Button>
          )}
          {!isActive && (
            <Button type="button" onClick={() => setActivePortfolioId(portfolio.id)}>
              Definir como ativa
            </Button>
          )}
          <Link to="/carteiras" className="rounded-2xl border border-[var(--border-soft)] bg-white px-4 py-2.5 text-sm font-semibold text-[var(--text-main)]">
            Voltar
          </Link>
        </div>
      </section>

      {(analysisLoading || pricesLoading) && (
        <Card title="Atualizando carteira">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--brand)] border-t-transparent" />
            <p className="text-sm text-[var(--text-muted)]">Carregando analise, precos e comparativos da carteira...</p>
          </div>
        </Card>
      )}

      {analysisError && (
        <Card title="Falha ao carregar dados">
          <p className="text-sm text-[var(--danger-text)]">{analysisError}</p>
        </Card>
      )}

      <PortfolioAnalysisAI portfolioId={portfolio.id} />

      <Card title="Adicionar ativos">
        <form onSubmit={addAsset} className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-5">
            <select
              value={selectedClass}
              onChange={(e) => { setSelectedClass(e.target.value); setAssetTicker(''); }}
              className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm"
            >
              <option value="">Tipo de ativo</option>
              {ASSET_CLASSES.map((cls) => (
                <option key={cls} value={cls}>{CLASS_LABELS[cls] || cls}</option>
              ))}
            </select>
            <select
              value={assetTicker}
              onChange={(e) => { setAssetTicker(e.target.value); }}
              className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm"
              disabled={!selectedClass}
            >
              <option value="">Selecionar ativo</option>
              {filteredAssets.map((asset) => (
                <option key={asset.ticker} value={asset.ticker}>
                  {asset.ticker} - {asset.name}
                </option>
              ))}
            </select>
            <Input type="number" min={0.01} step={0.01} value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} placeholder="Quantidade" />
            <Input type="number" min={0} step={0.01} value={avgPrice} onChange={(e) => setAvgPrice(e.target.value)} placeholder="Preco medio (opcional)" />
            <Button type="submit">Adicionar</Button>
          </div>
          <p className="text-xs text-[var(--text-muted)]">Selecione o tipo de ativo primeiro para filtrar as opcoes disponiveis.</p>
        </form>
      </Card>

      <Card title="Filtros e ordenacao" right={<ArrowDownUp size={16} className="text-[var(--brand)]" />}>
        <div className="grid gap-3 sm:grid-cols-3">
          <Input value={tableQuery} onChange={(e) => setTableQuery(e.target.value)} placeholder="Filtrar por ticker ou nome" />
          <select value={sortKey} onChange={(e) => updateSort(e.target.value as SortKey)} className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm">
            <option value="weight_pct">% da carteira</option>
            <option value="total_value">Valor atual</option>
            <option value="unrealized_pnl">Ganho/perda</option>
            <option value="current_price">Preco atual</option>
            <option value="quantity">Quantidade</option>
            <option value="ticker">Ticker</option>
          </select>
          <Button type="button" variant="ghost" onClick={() => setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))}>
            Ordem: {sortDirection === 'asc' ? 'Crescente' : 'Decrescente'}
          </Button>
        </div>
      </Card>

      {assetClassesWithPositions.length > 0 ? (
        assetClassesWithPositions.map((cls) => (
          <Card key={cls} title={CLASS_LABELS[cls] || cls}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[var(--text-muted)]">
                    <th className="py-2">Ticker</th>
                    <th>Quantidade</th>
                    <th>Preco medio</th>
                    <th>Preco atual</th>
                    <th>Valor total</th>
                    <th>P&L nao realizado</th>
                    <th>% Carteira</th>
                    <th>IA</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {positionsByClass[cls].map((pos) => {
                    const priceInfo = getPriceInfo(pos.ticker);
                    const opinionState = positionOpinions[pos.ticker];
                    const chartData = opinionState?.data
                      ? mergeChartSeries(
                          opinionState.data.historical_series,
                          opinionState.data.forecast_series,
                          opinionState.data.current_snapshot.current_price,
                        )
                      : [];
                    return (
                      <Fragment key={pos.ticker}>
                        <tr className="border-t border-[var(--border-soft)]">
                          <td className="py-3 font-semibold">{pos.ticker}</td>
                          <td>{pos.quantity}</td>
                          <td>{pos.avg_price ? `R$ ${pos.avg_price.toFixed(2)}` : '-'}</td>
                          <td>{priceInfo?.current_price != null ? `${priceInfo.currency === 'BRL' ? 'R$' : priceInfo.currency} ${priceInfo.current_price.toFixed(2)}` : '-'}</td>
                          <td>{fmtMoney(priceInfo?.total_value)}</td>
                          <td>
                            {priceInfo?.unrealized_pnl != null ? (
                              <span className={priceInfo.unrealized_pnl >= 0 ? 'text-green-600' : 'text-[var(--danger-text)]'}>
                                {fmtMoney(priceInfo.unrealized_pnl)} {priceInfo.unrealized_pnl_pct != null ? `(${priceInfo.unrealized_pnl_pct.toFixed(1)}%)` : ''}
                              </span>
                            ) : '-'}
                          </td>
                          <td>{priceInfo?.weight_pct != null ? `${priceInfo.weight_pct.toFixed(1)}%` : '-'}</td>
                          <td>
                            <button
                              type="button"
                              className="inline-flex items-center gap-2 rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-3 py-2 text-sm font-semibold text-[var(--text-main)] transition hover:border-[var(--brand)]"
                              onClick={() => togglePositionOpinion(pos.ticker)}
                            >
                              <Sparkles size={14} className="text-[var(--brand)]" />
                              {opinionState?.open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </button>
                          </td>
                          <td className="text-right">
                            <button type="button" className="text-sm font-semibold text-[var(--danger-text)]" onClick={() => handleRemovePosition(pos.ticker)}>
                              Remover
                            </button>
                          </td>
                        </tr>
                        {opinionState?.open && (
                          <tr className="border-t border-[var(--border-soft)] bg-[var(--bg-surface-strong)]/60">
                            <td colSpan={9} className="p-4">
                              {opinionState.loading && (
                                <div className="flex items-center gap-3">
                                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--brand)] border-t-transparent" />
                                  <p className="text-sm text-[var(--text-muted)]">Gerando analise do ativo...</p>
                                </div>
                              )}

                              {!opinionState.loading && opinionState.error && (
                                <p className="text-sm text-[var(--danger-text)]">{opinionState.error}</p>
                              )}

                              {!opinionState.loading && opinionState.data && (
                                <div className="space-y-4">
                                  <div className="rounded-[28px] border border-[var(--border-soft)] bg-[linear-gradient(135deg,rgba(61,77,156,0.06)_0%,rgba(255,255,255,0.96)_45%,rgba(199,85,155,0.08)_100%)] p-5 shadow-[var(--shadow-card)]">
                                    <div className="flex flex-wrap items-start justify-between gap-4">
                                      <div className="space-y-1">
                                        <p className="text-lg font-semibold text-[var(--text-main)]">
                                          {opinionState.data.ticker} ({opinionState.data.asset_name})
                                        </p>
                                        <p className="text-sm text-[var(--text-muted)]">
                                          {confidenceLabel(opinionState.data.confidence)} | Cenario: {opinionState.data.outlook_3m.scenario}
                                        </p>
                                        <p className="text-xs text-[var(--text-muted)]">
                                          Janela historica: {opinionState.data.historical_window.start_date} ate {opinionState.data.historical_window.end_date} | {opinionState.data.used_news_count} noticia(s) usada(s)
                                        </p>
                                        {opinionState.data.current_snapshot.asset_function && (
                                          <p className="text-xs text-[var(--text-muted)]">
                                            Funcao do ativo: {opinionState.data.current_snapshot.asset_function.replace('_', ' ')}
                                          </p>
                                        )}
                                      </div>
                                      {opinionState.data.current_snapshot.weight_pct != null && (
                                        <span className="rounded-full border border-[var(--border-soft)] bg-white/90 px-3 py-1.5 text-xs font-semibold text-[var(--text-main)] shadow-sm">
                                          {opinionState.data.current_snapshot.weight_pct.toFixed(1)}% da carteira
                                        </span>
                                      )}
                                    </div>

                                    <div className="mt-4 grid gap-3 lg:grid-cols-3">
                                      <section className="rounded-3xl border border-[var(--border-soft)] bg-white/90 p-4">
                                        <div className="flex flex-wrap items-center gap-3">
                                          <p className="text-sm font-semibold text-[var(--text-main)]">{historySectionTitle(opinionState.historyHorizon)}:</p>
                                          <div className="flex flex-wrap gap-2">
                                            {HISTORY_OPTIONS.map((option) => (
                                              <button
                                                key={option.key}
                                                type="button"
                                                onClick={() => loadPositionOpinion(pos.ticker, { historyHorizon: option.key, keepOpen: true })}
                                                className={horizonButtonClass(opinionState.historyHorizon === option.key)}
                                              >
                                                {option.label}
                                              </button>
                                            ))}
                                          </div>
                                        </div>
                                        <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">
                                          {opinionState.data.analysis_sections.recent_by_horizon[opinionState.historyHorizon]}
                                        </p>
                                      </section>
                                      <section className="rounded-3xl border border-[var(--border-soft)] bg-white/90 p-4">
                                        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--accent)]">Situacao atual</p>
                                        <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{opinionState.data.analysis_sections.current}</p>
                                      </section>
                                      <section className="rounded-3xl border border-[var(--border-soft)] bg-white/90 p-4">
                                        <div className="flex flex-wrap items-center gap-3">
                                          <p className="text-sm font-semibold text-[var(--text-main)]">Perspectiva:</p>
                                          <div className="flex flex-wrap gap-2">
                                            {OUTLOOK_OPTIONS.map((option) => (
                                              <button
                                                key={option.key}
                                                type="button"
                                                onClick={() => loadPositionOpinion(pos.ticker, { outlookHorizon: option.key, keepOpen: true })}
                                                className={horizonButtonClass(opinionState.outlookHorizon === option.key)}
                                              >
                                                {option.label}
                                              </button>
                                            ))}
                                          </div>
                                        </div>
                                        <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">
                                          {opinionState.data.analysis_sections.outlook_by_horizon[opinionState.outlookHorizon]}
                                        </p>
                                      </section>
                                    </div>
                                  </div>

                                  <section className="rounded-[28px] border border-[var(--border-soft)] bg-white p-5 shadow-[var(--shadow-card)]">
                                    <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
                                      <div className="space-y-2">
                                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Preco</p>
                                        <div className="flex flex-wrap items-end gap-3">
                                          <p className="text-4xl font-bold leading-none text-[var(--text-main)]">
                                            {fmtMoney(opinionState.data.current_snapshot.current_price, opinionState.data.current_snapshot.currency)}
                                          </p>
                                          <div className="pb-1">
                                            <span className={`text-sm font-semibold ${(opinionState.data.recent_performance.change_selected_pct ?? 0) >= 0 ? 'text-[var(--brand)]' : 'text-[var(--danger-text)]'}`}>
                                              {fmtPct(opinionState.data.recent_performance.change_selected_pct)}
                                            </span>
                                            <span className="ml-2 text-sm uppercase tracking-wider text-[var(--text-muted)]">
                                              vs {historyOptionLabel(opinionState.historyHorizon)}
                                            </span>
                                          </div>
                                        </div>
                                      </div>

                                      <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[320px]">
                                        <div className="space-y-2">
                                          <p className="text-sm font-semibold text-[var(--text-main)]">Ultimos</p>
                                          <div className="flex flex-wrap gap-2">
                                            {HISTORY_OPTIONS.map((option) => (
                                              <button
                                                key={option.key}
                                                type="button"
                                                onClick={() => loadPositionOpinion(pos.ticker, { historyHorizon: option.key, keepOpen: true })}
                                                className={horizonButtonClass(opinionState.historyHorizon === option.key)}
                                              >
                                                {option.label}
                                              </button>
                                            ))}
                                          </div>
                                        </div>

                                        <div className="space-y-2">
                                          <p className="text-sm font-semibold text-[var(--text-main)]">Perspectiva</p>
                                          <div className="flex flex-wrap gap-2">
                                            {OUTLOOK_OPTIONS.map((option) => (
                                              <button
                                                key={option.key}
                                                type="button"
                                                onClick={() => loadPositionOpinion(pos.ticker, { outlookHorizon: option.key, keepOpen: true })}
                                                className={horizonButtonClass(opinionState.outlookHorizon === option.key)}
                                              >
                                                {option.label}
                                              </button>
                                            ))}
                                          </div>
                                        </div>
                                      </div>
                                    </div>

                                    <div className="mt-6 h-[26rem] rounded-[24px] border border-[var(--border-soft)] bg-[linear-gradient(180deg,rgba(61,77,156,0.04)_0%,rgba(255,255,255,0.96)_24%,rgba(199,85,155,0.05)_100%)] p-4">
                                      {chartData.length ? (
                                        <ResponsiveContainer width="100%" height="100%">
                                          <ComposedChart data={chartData} margin={{ top: 18, right: 16, left: 8, bottom: 12 }}>
                                            <defs>
                                              <linearGradient id={`historyFill-${pos.ticker}`} x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="0%" stopColor="#3D4D9C" stopOpacity={0.22} />
                                                <stop offset="100%" stopColor="#3D4D9C" stopOpacity={0.02} />
                                              </linearGradient>
                                              <linearGradient id={`outlookFill-${pos.ticker}`} x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="0%" stopColor="#C7559B" stopOpacity={0.22} />
                                                <stop offset="100%" stopColor="#C7559B" stopOpacity={0.02} />
                                              </linearGradient>
                                            </defs>
                                            <CartesianGrid vertical={false} stroke="rgba(113,113,113,0.16)" />
                                            <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#717171' }} axisLine={false} tickLine={false} minTickGap={24} />
                                            <YAxis tick={{ fontSize: 11, fill: '#717171' }} axisLine={false} tickLine={false} width={72} domain={['auto', 'auto']} tickFormatter={(value) => fmtMoney(Number(value), opinionState.data!.current_snapshot.currency)} />
                                            <Tooltip content={({ active, payload, label }) => {
                                              if (!active || !payload?.length) return null;
                                              const dataPoint = payload[0]?.payload as ChartPoint | undefined;
                                              const displayValue = dataPoint?.precoAtual ?? dataPoint?.historico ?? dataPoint?.perspectiva ?? null;
                                              return (
                                                <div className="rounded-2xl border border-[var(--border-soft)] bg-white px-4 py-3 shadow-[var(--shadow-card)]">
                                                  <p className="text-xs font-semibold uppercase tracking-wider text-[var(--accent)]">{dataPoint?.isToday ? 'Hoje' : label}</p>
                                                  <p className="mt-1 text-sm font-semibold text-[var(--text-main)]">{fmtMoney(displayValue, opinionState.data!.current_snapshot.currency)}</p>
                                                </div>
                                              );
                                            }} />
                                            <Legend wrapperStyle={{ paddingTop: 8 }} />
                                            <Area type="monotone" dataKey="areaHistorico" stroke="none" fill={`url(#historyFill-${pos.ticker})`} isAnimationActive={false} connectNulls legendType="none" />
                                            <Area type="monotone" dataKey="areaPerspectiva" stroke="none" fill={`url(#outlookFill-${pos.ticker})`} isAnimationActive={false} connectNulls legendType="none" />
                                            <Line type="monotone" dataKey="historico" name="Historico" stroke="#3D4D9C" strokeWidth={3} dot={false} connectNulls isAnimationActive={false} />
                                            <Line type="monotone" dataKey="perspectiva" name="Perspectiva estimada" stroke="#C7559B" strokeWidth={3} dot={false} connectNulls isAnimationActive={false} />
                                            {chartData.some((point) => point.isToday) && (
                                              <>
                                                <ReferenceLine x={chartData.find((point) => point.isToday)?.label} stroke="rgba(199,85,155,0.55)" strokeDasharray="4 6" />
                                                <ReferenceDot x={chartData.find((point) => point.isToday)?.label} y={chartData.find((point) => point.isToday)?.precoAtual ?? undefined} r={6} fill="#C7559B" stroke="#ffffff" strokeWidth={3} />
                                              </>
                                            )}
                                          </ComposedChart>
                                        </ResponsiveContainer>
                                      ) : (
                                        <div className="flex h-full items-center justify-center text-sm text-[var(--text-muted)]">
                                          Sem serie suficiente para montar o grafico desse ativo.
                                        </div>
                                      )}
                                    </div>
                                    <p className="mt-3 text-xs text-[var(--text-muted)]">
                                      O grafico combina precos historicos e perspectiva estimada do Operum. A projecao nao representa garantia de preco futuro.
                                    </p>
                                  </section>

                                  {!!opinionState.data.source_groups.length && (
                                    <div className="space-y-2">
                                      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Fontes usadas</p>
                                      <div className="flex flex-wrap gap-2">
                                        {opinionState.data.source_groups.map((group) => (
                                          <button
                                            key={group.source_name}
                                            type="button"
                                            onClick={() => toggleSourceGroup(pos.ticker, group.source_name)}
                                            className="rounded-full border border-[var(--border-soft)] bg-white px-3 py-2 text-xs font-semibold text-[var(--text-main)] transition hover:border-[var(--brand)]"
                                          >
                                            {group.source_name} ({group.count})
                                          </button>
                                        ))}
                                      </div>
                                      <div className="space-y-3">
                                        {opinionState.data.source_groups
                                          .filter((group) => opinionState.expandedSources?.[group.source_name])
                                          .map((group) => (
                                            <div key={`${group.source_name}-panel`} className="rounded-2xl border border-[var(--border-soft)] bg-white p-3">
                                              <p className="text-sm font-semibold text-[var(--text-main)]">{group.source_name}</p>
                                              <div className="mt-3 space-y-2">
                                                {group.items.map((item) => (
                                                  <a
                                                    key={item.id}
                                                    href={item.source_url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="block rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3 transition hover:border-[var(--brand)]"
                                                  >
                                                    <p className="text-sm font-semibold text-[var(--text-main)]">{item.title}</p>
                                                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                                                      {new Date(item.published_at).toLocaleDateString('pt-BR')}
                                                      {item.role ? ` â€¢ ${item.role}` : ''}
                                                      {item.analysis_category ? ` â€¢ ${item.analysis_category}` : ''}
                                                    </p>
                                                  </a>
                                                ))}
                                              </div>
                                            </div>
                                          ))}
                                      </div>
                                    </div>
                                  )}

                                  {!opinionState.data.source_groups.length && (
                                    <p className="text-sm text-[var(--text-muted)]">
                                      Sem noticias suficientes para esse ativo. A leitura foi baseada mais em preco, benchmark e classe do ativo.
                                    </p>
                                  )}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        ))
      ) : (
        <Card title="Ativos">
          <p className="py-4 text-center text-sm text-[var(--text-muted)]">Nenhum ativo ainda. Adicione o primeiro abaixo.</p>
        </Card>
      )}

      <CompositionCharts positions={portfolio.positions} analysis={analysis} />
    </div>
  );
}
