import { FormEvent, Fragment, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Sparkles, ChevronDown, ChevronUp, ArrowDownUp } from 'lucide-react';
import { Button, Card, Input } from '../components/UI';
import { CompositionCharts } from '../components/CompositionCharts';
import { PortfolioAnalysisAI } from '../components/PortfolioAnalysisAI';
import { usePortfolios } from '../context/PortfoliosContext';
import { getPortfolioLabel } from '../utils/portfolios';
import api from '../utils/api';
import type { Asset, PortfolioAnalysis, PositionOpinion } from '../types';

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
  sparkline_20d: number[];
};

type PricesResponse = {
  portfolio_id: string;
  portfolio_name: string;
  total_value: number | null;
  total_unrealized_pnl: number | null;
  positions: PriceRow[];
};

const ASSET_CLASSES = ['BR_STOCK', 'FII', 'BDR', 'CRYPTO', 'US_STOCK', 'FIXED_INCOME'] as const;

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
};

type SortKey = 'ticker' | 'quantity' | 'current_price' | 'total_value' | 'weight_pct' | 'unrealized_pnl';

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

function Sparkline({ values }: { values: number[] }) {
  if (!values.length) return <span className="text-xs text-[var(--text-muted)]">-</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const points = values.map((value, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * 100;
    const y = 24 - ((value - min) / range) * 24;
    return `${x},${y}`;
  }).join(' ');
  const rising = values[values.length - 1] >= values[0];
  return (
    <svg viewBox="0 0 100 24" className="h-8 w-24 overflow-visible">
      <polyline
        fill="none"
        stroke={rising ? '#3D9C72' : '#C7559B'}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points}
      />
    </svg>
  );
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
      const priceInfo = prices?.positions.find((item) => item.ticker === pos.ticker);
      const asset = assets.find((item) => item.ticker === pos.ticker);
      const label = resolveDisplayClass(pos.asset_class, pos.ticker, assets);
      const haystack = `${pos.ticker} ${asset?.name ?? ''}`.toLowerCase();
      if (query && !haystack.includes(query)) continue;
      if (!grouped[label]) grouped[label] = [];
      grouped[label].push(pos);
      if (priceInfo) {
        // no-op: keeps parity with memo deps for sorting values
      }
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

  async function togglePositionOpinion(ticker: string) {
    if (!portfolio) return;
    const existing = positionOpinions[ticker];
    if (existing?.open) {
      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: { ...existing, open: false },
      }));
      return;
    }

    setPositionOpinions((prev) => ({
      ...prev,
      [ticker]: { ...existing, loading: true, open: true, error: undefined },
    }));

    try {
      const data = await api.get<PositionOpinion>(`/models/opinion/${portfolio.id}/positions/${ticker}`);
      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: { loading: false, open: true, data, expandedSources: {} },
      }));
    } catch (e) {
      setPositionOpinions((prev) => ({
        ...prev,
        [ticker]: { loading: false, open: true, error: e instanceof Error ? e.message : 'Erro ao gerar analise' },
      }));
    }
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
      setSortDirection((prev) => prev === 'asc' ? 'desc' : 'asc');
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
            {portfolio.positions.length} ativo(s) • Moeda base: {portfolio.base_currency}
            {prices?.total_value != null && ` • Valor total: ${fmtMoney(prices.total_value)}`}
            {prices?.total_unrealized_pnl != null && ` • P&L nao realizado: ${fmtMoney(prices.total_unrealized_pnl)}`}
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

      {analysis?.benchmark && (
        <Card title="Benchmark de referencia">
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="rounded-2xl bg-[var(--bg-surface-strong)] p-4">
              <p className="text-xs text-[var(--text-muted)]">Benchmark</p>
              <p className="mt-1 text-lg font-bold text-[var(--text-main)]">{analysis.benchmark.label}</p>
            </div>
            <div className="rounded-2xl bg-[var(--bg-surface-strong)] p-4">
              <p className="text-xs text-[var(--text-muted)]">Beta (estimativa)</p>
              <p className="mt-1 text-lg font-bold text-[var(--text-main)]">{analysis.beta != null ? analysis.beta.toFixed(2) : '-'}</p>
            </div>
            <div className="rounded-2xl bg-[var(--bg-surface-strong)] p-4">
              <p className="text-xs text-[var(--text-muted)]">Benchmark 3m</p>
              <p className="mt-1 text-lg font-bold text-[var(--text-main)]">{analysis.benchmark.return_63d_pct != null ? `${analysis.benchmark.return_63d_pct.toFixed(1)}%` : '-'}</p>
            </div>
            <div className="rounded-2xl bg-[var(--bg-surface-strong)] p-4">
              <p className="text-xs text-[var(--text-muted)]">VaR 95% (252d)</p>
              <p className="mt-1 text-lg font-bold text-[var(--text-main)]">{analysis.var_95 != null ? `${(analysis.var_95 * 100).toFixed(2)}%` : '-'}</p>
            </div>
          </div>
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
            <Input
              type="number"
              min={0.01}
              step={0.01}
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              placeholder="Quantidade"
            />
            <Input
              type="number"
              min={0}
              step={0.01}
              value={avgPrice}
              onChange={(e) => setAvgPrice(e.target.value)}
              placeholder="Preco medio (opcional)"
            />
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
          <Button type="button" variant="ghost" onClick={() => setSortDirection((prev) => prev === 'asc' ? 'desc' : 'asc')}>
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
                    <th>Mini historico</th>
                    <th>IA</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {positionsByClass[cls].map((pos) => {
                    const priceInfo = getPriceInfo(pos.ticker);
                    const opinionState = positionOpinions[pos.ticker];
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
                          <td><Sparkline values={priceInfo?.sparkline_20d ?? []} /></td>
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
                            <button
                              type="button"
                              className="text-sm font-semibold text-[var(--danger-text)]"
                              onClick={() => handleRemovePosition(pos.ticker)}
                            >
                              Remover
                            </button>
                          </td>
                        </tr>
                        {opinionState?.open && (
                          <tr className="border-t border-[var(--border-soft)] bg-[var(--bg-surface-strong)]/60">
                            <td colSpan={10} className="p-4">
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
                                  <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                      <p className="text-base font-semibold text-[var(--text-main)]">
                                        {opinionState.data.ticker} ({opinionState.data.asset_name})
                                      </p>
                                      <p className="text-xs text-[var(--text-muted)]">
                                        {confidenceLabel(opinionState.data.confidence)} • Cenario 3 meses: {opinionState.data.outlook_3m.scenario}
                                      </p>
                                      <p className="mt-1 text-xs text-[var(--text-muted)]">
                                        Janela historica: {opinionState.data.historical_window.start_date} ate {opinionState.data.historical_window.end_date} • {opinionState.data.used_news_count} noticia(s) usada(s)
                                      </p>
                                    </div>
                                    {opinionState.data.current_snapshot.weight_pct != null && (
                                      <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-[var(--text-main)]">
                                        {opinionState.data.current_snapshot.weight_pct.toFixed(1)}% da carteira
                                      </span>
                                    )}
                                  </div>

                                  <div className="grid gap-3 lg:grid-cols-4">
                                    <section className="rounded-2xl bg-white p-4">
                                      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Situacao atual</p>
                                      <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{opinionState.data.analysis_sections.current}</p>
                                    </section>
                                    <section className="rounded-2xl bg-white p-4">
                                      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Ultimos 3 meses</p>
                                      <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{opinionState.data.analysis_sections.recent}</p>
                                    </section>
                                    <section className="rounded-2xl bg-white p-4">
                                      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Perspectivas 3 meses</p>
                                      <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{opinionState.data.analysis_sections.outlook}</p>
                                    </section>
                                    <section className="rounded-2xl bg-white p-4">
                                      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Snapshot quantitativo</p>
                                      <div className="mt-2 space-y-2 text-sm text-[var(--text-main)]">
                                        <p>Beta 63d: {opinionState.data.recent_performance.beta_63d ?? '-'}</p>
                                        <p>Correlacao 63d: {opinionState.data.recent_performance.correlation_63d ?? '-'}</p>
                                        <p>Drawdown 90d: {opinionState.data.recent_performance.drawdown_90d_pct != null ? `${opinionState.data.recent_performance.drawdown_90d_pct}%` : '-'}</p>
                                        <p>Benchmark: {opinionState.data.recent_performance.benchmark_ticker ?? '-'}</p>
                                      </div>
                                    </section>
                                  </div>

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
                                                      {item.role ? ` • ${item.role}` : ''}
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
                                    <p className="text-sm text-[var(--text-muted)]">Sem noticias suficientes para esse ativo. A leitura foi baseada mais em preco e classe do ativo.</p>
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
