import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button, Card, Input } from '../components/UI';
import { CompositionCharts } from '../components/CompositionCharts';
import { PortfolioAnalysisAI } from '../components/PortfolioAnalysisAI';
import { usePortfolios } from '../context/PortfoliosContext';
import { getPortfolioLabel } from '../utils/portfolios';
import api from '../utils/api';
import type { Asset, PortfolioAnalysis } from '../types';

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
};

type PricesResponse = {
  portfolio_id: string;
  portfolio_name: string;
  total_value: number | null;
  positions: PriceRow[];
};

const ASSET_CLASSES = ['BR_STOCK', 'FII', 'BDR', 'CRYPTO', 'US_STOCK', 'FIXED_INCOME'] as const;

const CLASS_LABELS: Record<string, string> = {
  BR_STOCK: 'Ações Brasileiras',
  FII: 'Fundos Imobiliários',
  BDR: 'BDRs',
  CRYPTO: 'Criptomoedas',
  US_STOCK: 'Ações EUA',
  FIXED_INCOME: 'Renda Fixa',
};

function resolveDisplayClass(assetClass: string, ticker: string, assets: Asset[]): string {
  if (assetClass === 'US_STOCK') {
    const asset = assets.find((a) => a.ticker === ticker);
    if (asset?.sub_type === 'BDR') return 'BDR';
  }
  return assetClass;
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
  const [, setAnalysisLoading] = useState(false);
  const [, setAnalysisError] = useState<string | null>(null);
  const [prices, setPrices] = useState<PricesResponse | null>(null);
  const [pricesLoading, setPricesLoading] = useState(false);

  useEffect(() => {
    api.get<Asset[]>('/assets/universe').then(setAssets).catch(() => {});
  }, []);

  const portfolio = portfolios.find((item) => item.id === id);

  useEffect(() => {
    if (!portfolio) return;
    setAnalysisLoading(true);
    setAnalysisError(null);
    api.get<PortfolioAnalysis>(`/portfolios/${portfolio.id}/analysis`)
      .then(setAnalysis)
      .catch((e) => {
        setAnalysisError(e instanceof Error ? e.message : 'Erro ao carregar análise');
        setAnalysis(null);
      })
      .finally(() => setAnalysisLoading(false));
  }, [portfolio]);

  useEffect(() => {
    if (!portfolio) return;
    setPricesLoading(true);
    api.get<PricesResponse>(`/portfolios/${portfolio.id}/prices`)
      .then(setPrices)
      .catch(() => setPrices(null))
      .finally(() => setPricesLoading(false));
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
    const grouped: Record<string, typeof portfolio.positions> = {};
    for (const pos of portfolio.positions) {
      const cls = resolveDisplayClass(pos.asset_class, pos.ticker, assets);
      if (!grouped[cls]) grouped[cls] = [];
      grouped[cls].push(pos);
    }
    return grouped;
  }, [portfolio, assets]);

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

  if (!portfolio) {
    return (
      <Card title="Carteira não encontrada">
        <p className="text-sm text-[var(--text-muted)]">A carteira solicitada não existe ou foi removida.</p>
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
            {prices?.total_value != null && ` • Valor total: R$ ${prices.total_value.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`}
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

      {/* Análise com IA */}
      <PortfolioAnalysisAI portfolioId={portfolio.id} />

      {/* Adicionar ativos */}
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
              placeholder="Preço médio (opcional)"
            />
            <Button type="submit">Adicionar</Button>
          </div>
          <p className="text-xs text-[var(--text-muted)]">Selecione o tipo de ativo primeiro para filtrar as opções disponíveis.</p>
        </form>
      </Card>

      {/* Tabelas de posições por classe */}
      {assetClassesWithPositions.length > 0 ? (
        assetClassesWithPositions.map((cls) => (
          <Card key={cls} title={CLASS_LABELS[cls] || cls}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[var(--text-muted)]">
                    <th className="py-2">Ticker</th>
                    <th>Quantidade</th>
                    <th>Preço médio</th>
                    <th>Preço atual</th>
                    <th>Valor total</th>
                    <th>% Carteira</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {positionsByClass[cls].map((pos) => {
                    const priceInfo = getPriceInfo(pos.ticker);
                    return (
                      <tr key={pos.ticker} className="border-t border-[var(--border-soft)]">
                        <td className="py-3 font-semibold">{pos.ticker}</td>
                        <td>{pos.quantity}</td>
                        <td>{pos.avg_price ? `R$ ${pos.avg_price.toFixed(2)}` : '-'}</td>
                        <td>
                          {pricesLoading ? '-' : priceInfo?.current_price != null
                            ? `R$ ${priceInfo.current_price.toFixed(2)}`
                            : '-'}
                        </td>
                        <td>
                          {pricesLoading ? '-' : priceInfo?.total_value != null
                            ? `R$ ${priceInfo.total_value.toFixed(2)}`
                            : '-'}
                        </td>
                        <td>
                          {pricesLoading ? '-' : priceInfo?.weight_pct != null
                            ? `${priceInfo.weight_pct.toFixed(1)}%`
                            : '-'}
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

      {/* Composição (gráficos) no final */}
      <CompositionCharts positions={portfolio.positions} analysis={analysis} />
    </div>
  );
}
