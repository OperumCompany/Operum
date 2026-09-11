import { FormEvent, Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Sparkles, ChevronDown, ChevronUp, ArrowDownUp, Download, Pencil } from 'lucide-react';
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
import { PortfolioAnalysisAI, type PortfolioAnalysisAIHandle } from '../components/PortfolioAnalysisAI';
import { PortfolioEvolutionChart } from '../components/PortfolioEvolutionChart';
import { usePortfolios } from '../context/PortfoliosContext';
import { getPortfolioLabel } from '../utils/portfolios';
import api from '../utils/api';
import type { Asset, HorizonSeriesPoint, PositionOpinion } from '../types';

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

const ASSET_CLASSES = ['BR_STOCK', 'FII', 'BDR', 'CRYPTO', 'US_STOCK'] as const;
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

const PREFETCH_OPINION_PAIRS: Array<[HistoryHorizonKey, OutlookHorizonKey]> = [
  ['1w', '1w'],
  ['1m', '1m'],
  ['2m', '2m'],
];

const CLASS_LABELS: Record<string, string> = {
  BR_STOCK: 'Ações brasileiras',
  FII: 'Fundos imobiliários',
  BDR: 'BDRs',
  CRYPTO: 'Criptomoedas',
  US_STOCK: 'Ações EUA',
};

type OpinionState = {
  data?: PositionOpinion;
  cache?: OpinionCache;
  loading: boolean;
  error?: string;
  open: boolean;
  expandedSources?: Record<string, boolean>;
  prefetched?: OpinionFlags;
  historyHorizon: '1w' | '1m' | '2m' | '3m';
  outlookHorizon: '1w' | '1m' | '2m' | '3m';
};

type SortKey = 'ticker' | 'quantity' | 'current_price' | 'total_value' | 'weight_pct' | 'unrealized_pnl';
type HistoryHorizonKey = OpinionState['historyHorizon'];
type OutlookHorizonKey = OpinionState['outlookHorizon'];
type OpinionCacheKey = `${HistoryHorizonKey}:${OutlookHorizonKey}`;
type OpinionCache = Partial<Record<OpinionCacheKey, PositionOpinion>>;
type OpinionFlags = Partial<Record<OpinionCacheKey, boolean>>;
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
  if (confidence === 'alta') return 'Confiança alta';
  if (confidence === 'media') return 'Confiança média';
  return 'Confiança baixa';
}

function cleanText(value: string | null | undefined) {
  if (!value) return '';
  let repaired = value;
  for (let i = 0; i < 3; i += 1) {
    if (!/[ÃÂâ]/.test(repaired)) break;
    try {
      const next = decodeURIComponent(escape(repaired));
      if (next === repaired) break;
      repaired = next;
    } catch {
      break;
    }
  }
  return repaired;
}

function fmtMoney(value: number | null | undefined, currency = 'BRL') {
  if (value == null) return '-';
  const prefix = currency === 'BRL' ? 'R$' : currency;
  return `${prefix} ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(value: number | null | undefined) {
  if (value == null) return '-';
  return `${value >= 0 ? '+' : ''}${value.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function historyOptionLabel(horizon: HistoryHorizonKey) {
  return HISTORY_OPTIONS.find((option) => option.key === horizon)?.label ?? '3 meses';
}

function opinionCacheKey(historyHorizon: HistoryHorizonKey, outlookHorizon: OutlookHorizonKey): OpinionCacheKey {
  return `${historyHorizon}:${outlookHorizon}`;
}

function horizonButtonClass(isActive: boolean) {
  return `rounded-full px-3 py-1.5 text-xs font-semibold transition ${
    isActive
      ? 'bg-[var(--accent-soft)] text-[var(--accent)] ring-1 ring-[var(--accent)]'
      : 'border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] text-[var(--text-main)] hover:border-[var(--accent)]'
  }`;
}

function formatChartDate(value: string) {
  const date = parseChartDate(value);
  if (!date) return value;
  return date.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
  });
}

function parseChartDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const normalized = value.includes('T') ? value : `${value}T00:00:00`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function isValidSeriesPoint(point: HorizonSeriesPoint | null | undefined): point is HorizonSeriesPoint {
  return Boolean(point && parseChartDate(point.date) && Number.isFinite(point.value));
}

function addBusinessDays(dateValue: string, days: number): string | null {
  const date = parseChartDate(dateValue);
  if (!date) return null;
  let added = 0;
  while (added < days) {
    date.setDate(date.getDate() + 1);
    const day = date.getDay();
    if (day !== 0 && day !== 6) {
      added += 1;
    }
  }
  return date.toISOString().slice(0, 10);
}

function outlookPointLimit(horizon: OutlookHorizonKey) {
  return {
    '1w': 5,
    '1m': 21,
    '2m': 42,
    '3m': 63,
  }[horizon];
}

function normalizeForecastSeries(
  historical: HorizonSeriesPoint[],
  forecast: HorizonSeriesPoint[],
  currentPrice: number | null | undefined,
  outlookHorizon: OutlookHorizonKey,
): HorizonSeriesPoint[] {
  const cleanHistorical = historical.filter(isValidSeriesPoint);
  const cleanForecast = forecast.filter(isValidSeriesPoint);
  if (!cleanForecast.length) return [];

  const historicalAnchor = cleanHistorical.length ? cleanHistorical[cleanHistorical.length - 1] : null;
  const forecastAnchor = cleanForecast[0];
  const anchorDate = historicalAnchor?.date ?? forecastAnchor.date;
  const anchorValue = currentPrice ?? historicalAnchor?.value ?? forecastAnchor.value;
  if (!parseChartDate(anchorDate) || !Number.isFinite(anchorValue)) return [];
  const futureValues = cleanForecast.slice(1, outlookPointLimit(outlookHorizon) + 1);

  return [
    { date: anchorDate, value: anchorValue },
    ...futureValues.flatMap((point, index) => {
      const date = addBusinessDays(anchorDate, index + 1);
      return date ? [{ date, value: point.value }] : [];
    }),
  ];
}

function mergeChartSeries(
  historical: HorizonSeriesPoint[],
  forecast: HorizonSeriesPoint[],
  currentPrice: number | null | undefined,
  outlookHorizon: OutlookHorizonKey,
): ChartPoint[] {
  const cleanHistorical = historical.filter(isValidSeriesPoint);
  const historicalMap = new Map(cleanHistorical.map((point) => [point.date, point.value]));
  const normalizedForecast = normalizeForecastSeries(cleanHistorical, forecast, currentPrice, outlookHorizon);
  const forecastMap = new Map(normalizedForecast.map((point) => [point.date, point.value]));
  const dates = Array.from(new Set([...historicalMap.keys(), ...forecastMap.keys()]))
    .filter((date) => parseChartDate(date))
    .sort();
  const todayDate = cleanHistorical.length
    ? cleanHistorical[cleanHistorical.length - 1].date
    : normalizedForecast.length
      ? normalizedForecast[0].date
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
  const [purchaseDate, setPurchaseDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [nameDraft, setNameDraft] = useState('');
  const [editingName, setEditingName] = useState(false);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [dataError, setDataError] = useState<string | null>(null);
  const [prices, setPrices] = useState<PricesResponse | null>(null);
  const [pricesLoading, setPricesLoading] = useState(false);
  const [positionOpinions, setPositionOpinions] = useState<Record<string, OpinionState>>({});
  const positionOpinionsRef = useRef<Record<string, OpinionState>>({});
  const opinionRequestsRef = useRef<Record<string, Partial<Record<OpinionCacheKey, Promise<PositionOpinion>>>>>({});
  const portfolioAnalysisRef = useRef<PortfolioAnalysisAIHandle>(null);
  const portfolioAnalysisSectionRef = useRef<HTMLDivElement>(null);
  const [tableQuery, setTableQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('weight_pct');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    api.get<Asset[]>('/assets/universe').then(setAssets).catch(() => {});
  }, []);

  useEffect(() => {
    positionOpinionsRef.current = positionOpinions;
  }, [positionOpinions]);

  const portfolio = portfolios.find((item) => item.id === id);

  useEffect(() => {
    if (!portfolio) return;
    setPricesLoading(true);
    setDataError(null);
    api.get<PricesResponse>(`/portfolios/${portfolio.id}/prices`)
      .then(setPrices)
      .catch((e) => {
        const msg = e instanceof Error ? e.message : 'Erro ao carregar dados da carteira';
        setDataError(msg);
        setPrices(null);
      })
      .finally(() => {
        setPricesLoading(false);
      });
  }, [portfolio]);

  const filteredAssets = useMemo(() => {
    const availableAssets = portfolio?.kind === 'example' ? assets : assets.filter((asset) => asset.source !== 'example');
    if (!selectedClass) return availableAssets;
    if (selectedClass === 'BDR') {
      return availableAssets.filter((a) => a.asset_class === 'US_STOCK' && a.sub_type === 'BDR');
    }
    return availableAssets.filter((a) => a.asset_class === selectedClass);
  }, [assets, portfolio?.kind, selectedClass]);

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
        occurred_at: purchaseDate,
      });
      setQuantity(10);
      setAvgPrice('');
      setAssetTicker('');
      setPositionOpinions({});
      setHistoryRefreshKey((current) => current + 1);
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

  function requestPositionOpinion(
    ticker: string,
    historyHorizon: HistoryHorizonKey,
    outlookHorizon: OutlookHorizonKey,
  ) {
    if (!portfolio) {
      return Promise.reject(new Error('Carteira não encontrada'));
    }
    const key = opinionCacheKey(historyHorizon, outlookHorizon);
    const tickerRequests = opinionRequestsRef.current[ticker] ?? {};
    const existingRequest = tickerRequests[key];
    if (existingRequest) return existingRequest;

    const request = api
      .get<PositionOpinion>(
        `/models/opinion/${portfolio.id}/positions/${ticker}?history_horizon=${historyHorizon}&outlook_horizon=${outlookHorizon}`,
      )
      .finally(() => {
        delete opinionRequestsRef.current[ticker]?.[key];
      });
      setHistoryRefreshKey((current) => current + 1);

    tickerRequests[key] = request;
    opinionRequestsRef.current[ticker] = tickerRequests;
    return request;
  }

  async function prefetchPositionOpinion(ticker: string) {
    for (const [historyHorizon, outlookHorizon] of PREFETCH_OPINION_PAIRS) {
      const key = opinionCacheKey(historyHorizon, outlookHorizon);
      const current = positionOpinionsRef.current[ticker];
      if (current?.cache?.[key] || current?.prefetched?.[key]) continue;

      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: {
          ...prev[ticker],
          prefetched: {
            ...(prev[ticker]?.prefetched ?? {}),
            [key]: true,
          },
        },
      }));

      try {
        const data = await requestPositionOpinion(ticker, historyHorizon, outlookHorizon);
        setPositionOpinions((prev) => ({
          ...prev,
          [ticker]: {
            ...prev[ticker],
            cache: {
              ...(prev[ticker]?.cache ?? {}),
              [key]: data,
            },
          },
        }));
      } catch {
        // Prefetch is only an optimization; direct user actions still surface errors.
      }
    }
  }

  async function loadPositionOpinion(
    ticker: string,
    options?: Partial<Pick<OpinionState, 'historyHorizon' | 'outlookHorizon'>> & { keepOpen?: boolean },
  ) {
    if (!portfolio) return;
    const existing = positionOpinionsRef.current[ticker];
    const historyHorizon = options?.historyHorizon ?? existing?.historyHorizon ?? '3m';
    const outlookHorizon = options?.outlookHorizon ?? existing?.outlookHorizon ?? '3m';
    const key = opinionCacheKey(historyHorizon, outlookHorizon);
    const cached = existing?.cache?.[key];

    if (cached) {
      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: {
          ...prev[ticker],
          loading: false,
          open: options?.keepOpen ?? true,
          error: undefined,
          data: cached,
          historyHorizon,
          outlookHorizon,
        },
      }));
      return;
    }

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
      const data = await requestPositionOpinion(ticker, historyHorizon, outlookHorizon);
      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: {
          ...prev[ticker],
          loading: false,
          open: true,
          data,
          cache: {
            ...(prev[ticker]?.cache ?? {}),
            [key]: data,
          },
          expandedSources: prev[ticker]?.expandedSources ?? {},
          historyHorizon,
          outlookHorizon,
        },
      }));
      if (key === opinionCacheKey('3m', '3m')) {
        void prefetchPositionOpinion(ticker);
      }
    } catch (e) {
      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: {
          ...prev[ticker],
          loading: false,
          open: true,
          error: e instanceof Error ? e.message : 'Erro ao gerar análise',
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
      <Card title="Carteira não encontrada">
        <p className="text-sm text-[var(--text-muted)]">A carteira solicitada não existe ou foi removida.</p>
        <Button type="button" className="mt-4" onClick={() => navigate('/app/carteiras')}>
          Voltar para carteiras
        </Button>
      </Card>
    );
  }

  const isActive = activePortfolioId === portfolio.id;
  const hasUnknownCost = (prices?.positions ?? []).some((position) => position.avg_price == null || position.total_value == null);
  const investedCost = prices && !hasUnknownCost
    ? prices.positions.reduce((sum, position) => sum + ((position.avg_price ?? 0) * position.quantity), 0)
    : null;
  const portfolioPnlPct = prices?.total_value != null && investedCost != null && investedCost > 0
    ? ((prices.total_value / investedCost) - 1) * 100
    : null;
  const allocationByClass = Object.entries(
    (prices?.positions ?? []).reduce<Record<string, number>>((acc, position) => {
      if (position.total_value != null) acc[position.asset_class] = (acc[position.asset_class] ?? 0) + position.total_value;
      return acc;
    }, {}),
  ).sort((a, b) => b[1] - a[1]);

  async function generatePortfolioAnalysis() {
    portfolioAnalysisSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    await portfolioAnalysisRef.current?.generate();
  }

  return (
    <div className="portfolio-detail-page space-y-5">
      <section className="no-print flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
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
            <div className="flex items-center gap-2">
              <h1 className="truncate text-3xl font-bold sm:text-4xl">{cleanText(getPortfolioLabel(portfolio))}</h1>
              <button type="button" className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--bg-surface-muted)]" onClick={() => { setEditingName(true); setNameDraft(portfolio.name); }} aria-label="Editar nome"><Pencil size={16} /></button>
            </div>
          )}
          <p className="mt-2 text-sm text-[var(--text-muted)]">Visão completa dos seus ativos, aportes e análises.</p>
        </div>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          {!isActive && (
            <Button type="button" variant="ghost" onClick={() => setActivePortfolioId(portfolio.id)}>
              Definir como ativa
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={() => window.print()} disabled={pricesLoading}><Download size={16} />Exportar relatório</Button>
          <Button type="button" variant="ai" onClick={() => { void generatePortfolioAnalysis(); }}><Sparkles size={16} />Gerar análise por IA</Button>
        </div>
      </section>

      {portfolio.kind === 'example' && (
        <section className="no-print rounded-[24px] border border-[var(--brand)]/20 bg-[var(--brand)]/5 p-4">
          <div className="flex items-start gap-3">
            <Sparkles size={18} className="mt-0.5 shrink-0 text-[var(--brand)]" />
            <div><p className="font-semibold text-[var(--text-main)]">Ambiente demonstrativo</p><p className="mt-1 text-sm leading-6 text-[var(--text-muted)]">Preços, evolução e análises desta carteira são simulados. Suas alterações ficam salvas somente nesta demonstração e não consomem serviços externos.</p></div>
          </div>
        </section>
      )}

      <section className="portfolio-report-heading hidden print:block">
        <p className="eyebrow">Relatório da carteira</p>
        <h1 className="mt-2 text-3xl font-bold">{cleanText(getPortfolioLabel(portfolio))}</h1>
        <p className="mt-1 text-sm">Gerado em {new Date().toLocaleString('pt-BR')}</p>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(280px,.55fr)]">
        <Card className="print-keep overflow-hidden !border-[rgba(223,80,242,.2)] !bg-[linear-gradient(135deg,var(--bg-surface)_20%,rgba(223,80,242,.10)_100%)]">
          <p className="eyebrow">Valor atual da carteira</p>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <p className="font-data text-4xl font-semibold tracking-[-0.04em] sm:text-5xl">{fmtMoney(prices?.total_value, portfolio.base_currency)}</p>
            {portfolioPnlPct != null && <span className={`mb-1 text-sm font-semibold ${portfolioPnlPct >= 0 ? 'text-emerald-600' : 'text-[var(--danger-text)]'}`}>{fmtPct(portfolioPnlPct)}</span>}
          </div>
          <div className="mt-7 grid gap-4 border-t border-[var(--border-soft)] pt-5 sm:grid-cols-3">
            <div><p className="text-xs text-[var(--text-muted)]">Total investido</p><p className="mt-1 font-data font-semibold">{investedCost != null && investedCost > 0 ? fmtMoney(investedCost, portfolio.base_currency) : '-'}</p></div>
            <div><p className="text-xs text-[var(--text-muted)]">P&L não realizado</p><p className={`mt-1 font-data font-semibold ${(prices?.total_unrealized_pnl ?? 0) >= 0 ? 'text-emerald-600' : 'text-[var(--danger-text)]'}`}>{hasUnknownCost ? '-' : fmtMoney(prices?.total_unrealized_pnl, portfolio.base_currency)}</p></div>
            <div><p className="text-xs text-[var(--text-muted)]">Ativos</p><p className="mt-1 font-data font-semibold">{portfolio.positions.length}</p></div>
          </div>
        </Card>

        <Card className="print-keep" title="Alocação">
          {allocationByClass.length ? <div className="space-y-4">{allocationByClass.map(([assetClass, value], index) => {
            const percentage = prices?.total_value ? (value / prices.total_value) * 100 : 0;
            const colors = ['#684CF2', '#DF50F2', '#941289', '#A896FF', '#B133A3'];
            return <div key={assetClass}><div className="flex items-center justify-between gap-3 text-sm"><span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: colors[index % colors.length] }} />{CLASS_LABELS[assetClass] ?? assetClass}</span><span className="font-data font-semibold">{percentage.toFixed(1)}%</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--bg-surface-high)]"><span className="block h-full rounded-full" style={{ width: `${percentage}%`, background: colors[index % colors.length] }} /></div></div>;
          })}</div> : <p className="text-sm text-[var(--text-muted)]">Sem valores disponíveis para calcular a alocação.</p>}
        </Card>
      </div>

      {pricesLoading && (
        <Card title="Atualizando carteira">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--brand)] border-t-transparent" />
            <p className="text-sm text-[var(--text-muted)]">Carregando preços e resumo da carteira...</p>
          </div>
        </Card>
      )}

      {dataError && (
        <Card title="Falha ao carregar dados">
          <p className="text-sm text-[var(--danger-text)]">{dataError}</p>
        </Card>
      )}

      <PortfolioEvolutionChart portfolioId={portfolio.id} currency={portfolio.base_currency} refreshKey={historyRefreshKey} defaultPeriod={portfolio.kind === 'example' ? '1y' : '6m'} />

      <Card className="no-print" title="Adicionar ativo ou aporte">
        <form onSubmit={addAsset} className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
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
                  {asset.ticker} - {cleanText(asset.name)}
                </option>
              ))}
            </select>
            <Input type="number" min={0.01} step={0.01} value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} placeholder="Quantidade" required />
            <Input type="number" min={0} step={0.01} value={avgPrice} onChange={(e) => setAvgPrice(e.target.value)} placeholder="Preço de aquisição" required />
            <Input type="date" max={new Date().toISOString().slice(0, 10)} value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} aria-label="Data do aporte" required />
            <Button type="submit">Adicionar</Button>
          </div>
          <p className="text-xs text-[var(--text-muted)]">Selecione o tipo de ativo primeiro para filtrar as opções disponíveis.</p>
        </form>
      </Card>

      <Card className="no-print" title="Filtrar ativos" right={<ArrowDownUp size={16} className="text-[var(--brand)]" />}>
        <div className="grid gap-3 sm:grid-cols-3">
          <Input value={tableQuery} onChange={(e) => setTableQuery(e.target.value)} placeholder="Filtrar por ticker ou nome" />
          <select value={sortKey} onChange={(e) => updateSort(e.target.value as SortKey)} className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm">
            <option value="weight_pct">% da carteira</option>
            <option value="total_value">Valor atual</option>
            <option value="unrealized_pnl">Ganho/perda</option>
            <option value="current_price">Preço atual</option>
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
          <Card key={cls} className="print-keep" title={CLASS_LABELS[cls] || cls}>
            <div className="overflow-x-auto">
              <table className="portfolio-holdings w-full text-sm">
                <thead>
                  <tr className="text-left text-[var(--text-muted)]">
                    <th className="py-2">Ticker</th>
                    <th>Quantidade</th>
                    <th>Preço médio</th>
                    <th>Preço atual</th>
                    <th>Valor total</th>
                    <th>P&L não realizado</th>
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
                            opinionState.outlookHorizon,
                          )
                        : [];
                    return (
                      <Fragment key={pos.ticker}>
                        <tr className="portfolio-position-row border-t border-[var(--border-soft)]">
                          <td data-label="Ativo" className="py-3 font-semibold">{pos.ticker}</td>
                          <td data-label="Quantidade">{pos.quantity}</td>
                          <td data-label="Preço médio">{pos.avg_price ? `R$ ${pos.avg_price.toFixed(2)}` : '-'}</td>
                          <td data-label="Preço atual">{priceInfo?.current_price != null ? `${priceInfo.currency === 'BRL' ? 'R$' : priceInfo.currency} ${priceInfo.current_price.toFixed(2)}` : '-'}</td>
                          <td data-label="Valor total">{fmtMoney(priceInfo?.total_value)}</td>
                          <td data-label="P&L">
                            {priceInfo?.unrealized_pnl != null ? (
                              <span className={priceInfo.unrealized_pnl >= 0 ? 'text-green-600' : 'text-[var(--danger-text)]'}>
                                {fmtMoney(priceInfo.unrealized_pnl)} {priceInfo.unrealized_pnl_pct != null ? `(${priceInfo.unrealized_pnl_pct.toFixed(1)}%)` : ''}
                              </span>
                            ) : '-'}
                          </td>
                          <td data-label="% Carteira">{priceInfo?.weight_pct != null ? `${priceInfo.weight_pct.toFixed(1)}%` : '-'}</td>
                          <td data-label="Análise">
                            <button
                              type="button"
                              className="inline-flex items-center gap-2 rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-3 py-2 text-sm font-semibold text-[var(--text-main)] transition hover:border-[var(--brand)]"
                              onClick={() => togglePositionOpinion(pos.ticker)}
                            >
                              <Sparkles size={14} className="text-[var(--brand)]" />
                              {opinionState?.open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </button>
                          </td>
                          <td data-label="Ação" className="text-right">
                            <button type="button" className="text-sm font-semibold text-[var(--danger-text)]" onClick={() => handleRemovePosition(pos.ticker)}>
                              Remover
                            </button>
                          </td>
                        </tr>
                        {opinionState?.open && (
                          <tr className="portfolio-analysis-row border-t border-[var(--border-soft)] bg-[var(--bg-surface-strong)]/60">
                            <td colSpan={9} className="p-4">
                              {opinionState.loading && (
                                <div className="flex items-center gap-3">
                                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--brand)] border-t-transparent" />
                                  <p className="text-sm text-[var(--text-muted)]">
                                    {opinionState.data ? 'Atualizando análise do ativo...' : 'Gerando análise do ativo...'}
                                  </p>
                                </div>
                              )}

                              {!opinionState.loading && opinionState.error && (
                                <p className="text-sm text-[var(--danger-text)]">{opinionState.error}</p>
                              )}

                              {opinionState.data && (
                                <div className="space-y-4">
                                  <div className="rounded-[28px] border border-[var(--border-soft)] bg-[linear-gradient(135deg,rgba(61,77,156,0.06)_0%,rgba(255,255,255,0.96)_45%,rgba(199,85,155,0.08)_100%)] p-5 shadow-[var(--shadow-card)]">
                                    <div className="flex flex-wrap items-start justify-between gap-4">
                                      <div className="space-y-1">
                                        <p className="text-lg font-semibold text-[var(--text-main)]">
                                          {opinionState.data.ticker} ({cleanText(opinionState.data.asset_name)})
                                        </p>
                                        <p className="text-sm text-[var(--text-muted)]">
                                          {confidenceLabel(opinionState.data.confidence)} | Cenário: {cleanText(opinionState.data.outlook_3m.scenario)}
                                        </p>
                                        <p className="text-xs text-[var(--text-muted)]">
                                          Janela histórica: {opinionState.data.historical_window.start_date} até {opinionState.data.historical_window.end_date} | {opinionState.data.used_news_count} notícia(s) usada(s)
                                        </p>
                                        {opinionState.data.current_snapshot.asset_function && (
                                          <p className="text-xs text-[var(--text-muted)]">
                                            Função do ativo: {cleanText(opinionState.data.current_snapshot.asset_function.replace('_', ' '))}
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
                                          <p className="text-sm font-semibold text-[var(--text-main)]">
                                            {opinionState.historyHorizon === '1w' ? 'Última 1 semana' : `Últimos ${historyOptionLabel(opinionState.historyHorizon)}`}:
                                          </p>
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
                                        <p className="mt-3 text-sm leading-relaxed text-[var(--text-main)]">
                                          {cleanText(opinionState.data.analysis_sections.box_history_by_horizon?.[opinionState.historyHorizon] ?? opinionState.data.analysis_sections.recent_by_horizon[opinionState.historyHorizon])}
                                        </p>
                                      </section>
                                      <section className="rounded-3xl border border-[var(--border-soft)] bg-white/90 p-4">
                                        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--accent)]">Situação atual</p>
                                        <p className="mt-3 text-sm leading-relaxed text-[var(--text-main)]">
                                          {cleanText(opinionState.data.analysis_sections.box_current ?? opinionState.data.analysis_sections.current)}
                                        </p>
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
                                        <p className="mt-3 text-sm leading-relaxed text-[var(--text-main)]">
                                          {cleanText(opinionState.data.analysis_sections.box_outlook_by_horizon?.[opinionState.outlookHorizon] ?? opinionState.data.analysis_sections.outlook_by_horizon[opinionState.outlookHorizon])}
                                        </p>
                                      </section>
                                    </div>
                                  </div>

                                  <section className="rounded-[28px] border border-[var(--border-soft)] bg-white p-5 shadow-[var(--shadow-card)]">
                                    <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
                                      <div className="space-y-2">
                                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Preço</p>
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
                                          <p className="text-sm font-semibold text-[var(--text-main)]">Últimos</p>
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
                                                <stop offset="0%" stopColor="#684CF2" stopOpacity={0.22} />
                                                <stop offset="100%" stopColor="#684CF2" stopOpacity={0.02} />
                                              </linearGradient>
                                              <linearGradient id={`outlookFill-${pos.ticker}`} x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="0%" stopColor="#DF50F2" stopOpacity={0.22} />
                                                <stop offset="100%" stopColor="#DF50F2" stopOpacity={0.02} />
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
                                            <Line type="monotone" dataKey="historico" name="Histórico" stroke="#684CF2" strokeWidth={3} dot={false} connectNulls isAnimationActive={false} />
                                            <Line type="monotone" dataKey="perspectiva" name="Perspectiva estimada" stroke="#DF50F2" strokeWidth={3} dot={false} connectNulls isAnimationActive={false} />
                                            {chartData.some((point) => point.isToday) && (
                                              <>
                                                <ReferenceLine x={chartData.find((point) => point.isToday)?.label} stroke="rgba(199,85,155,0.55)" strokeDasharray="4 6" />
                                                <ReferenceDot x={chartData.find((point) => point.isToday)?.label} y={chartData.find((point) => point.isToday)?.precoAtual ?? undefined} r={6} fill="#DF50F2" stroke="#ffffff" strokeWidth={3} />
                                              </>
                                            )}
                                          </ComposedChart>
                                        </ResponsiveContainer>
                                      ) : (
                                        <div className="flex h-full items-center justify-center text-sm text-[var(--text-muted)]">
                                          Sem série suficiente para montar o gráfico desse ativo.
                                        </div>
                                      )}
                                    </div>
                                    <p className="mt-3 text-xs text-[var(--text-muted)]">
                                      O gráfico combina preços históricos e perspectiva estimada do Operum. A projeção não representa garantia de preço futuro.
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
                                            {cleanText(group.source_name)} ({group.count})
                                          </button>
                                        ))}
                                      </div>
                                      <div className="space-y-3">
                                        {opinionState.data.source_groups
                                          .filter((group) => opinionState.expandedSources?.[group.source_name])
                                          .map((group) => (
                                            <div key={`${group.source_name}-panel`} className="rounded-2xl border border-[var(--border-soft)] bg-white p-3">
                                              <p className="text-sm font-semibold text-[var(--text-main)]">{cleanText(group.source_name)}</p>
                                              <div className="mt-3 space-y-2">
                                                {group.items.map((item) => (
                                                  <a
                                                    key={item.id}
                                                    href={item.source_url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="block rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3 transition hover:border-[var(--brand)]"
                                                  >
                                                    <p className="text-sm font-semibold text-[var(--text-main)]">{cleanText(item.title)}</p>
                                                    <p className="hidden">
                                                      {new Date(item.published_at).toLocaleDateString('pt-BR')}
                                                      {item.role ? ` • ${item.role}` : ''}
                                                      {item.analysis_category ? ` • ${item.analysis_category}` : ''}
                                                    </p>
                                                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                                                      {[
                                                        new Date(item.published_at).toLocaleDateString('pt-BR'),
                                                        item.role ? cleanText(item.role) : null,
                                                        item.analysis_category ? cleanText(item.analysis_category) : null,
                                                      ].filter(Boolean).join(' • ')}
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
                                      Sem notícias suficientes para esse ativo. A leitura foi baseada mais em preço, benchmark e classe do ativo.
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

      <div ref={portfolioAnalysisSectionRef} className="no-print scroll-mt-24">
        <PortfolioAnalysisAI ref={portfolioAnalysisRef} portfolioId={portfolio.id} />
      </div>

      <p className="portfolio-report-disclaimer hidden border-t border-[var(--border-soft)] pt-4 text-xs leading-5 print:block">
        Este relatório apresenta um retrato informativo da carteira e não constitui recomendação de compra ou venda de ativos. Valores dependem da disponibilidade das cotações.
      </p>
    </div>
  );
}
