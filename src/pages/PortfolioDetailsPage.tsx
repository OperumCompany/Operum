import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button, Card, Input } from '../components/UI';
import { usePortfolios } from '../context/PortfoliosContext';
import { PortfolioMetrics } from '../components/PortfolioMetrics';
import { CompositionCharts } from '../components/CompositionCharts';
import { getPortfolioLabel } from '../utils/portfolios';
import api from '../utils/api';
import type { Asset, PortfolioAnalysis } from '../types';

export function PortfolioDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { portfolios, activePortfolioId, setActivePortfolioId, addPosition, removePosition, updatePortfolio } = usePortfolios();
  const [assetTicker, setAssetTicker] = useState('');
  const [quantity, setQuantity] = useState(10);
  const [avgPrice, setAvgPrice] = useState('');
  const [nameDraft, setNameDraft] = useState('');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

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

  async function savePortfolioName(e: FormEvent) {
    e.preventDefault();
    if (!portfolio || !nameDraft.trim()) return;
    try {
      await updatePortfolio(portfolio.id, { name: nameDraft.trim() });
      setNameDraft('');
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
          <h2 className="mt-2 text-3xl font-bold">{getPortfolioLabel(portfolio)}</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            {portfolio.positions.length} ativo(s) • Moeda base: {portfolio.base_currency}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
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

      <PortfolioMetrics analysis={analysis} />
      {analysisLoading && <p className="text-sm text-[var(--text-muted)]">Carregando análise...</p>}
      {analysisError && <p className="text-sm text-[var(--danger-text)]">{analysisError}</p>}

      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.95fr]">
        <div className="space-y-4">
          <Card title="Editar nome">
            <form onSubmit={savePortfolioName} className="space-y-3">
              <Input placeholder={portfolio.name} value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} />
              <Button type="submit">Salvar</Button>
            </form>
          </Card>

          <Card title="Adicionar ativos">
            <form onSubmit={addAsset} className="grid gap-2 sm:grid-cols-4">
              <select
                value={assetTicker}
                onChange={(e) => { setAssetTicker(e.target.value); const asset = assets.find((a) => a.ticker === e.target.value); if (asset) setAvgPrice(''); }}
                className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm"
              >
                <option value="">Selecionar ativo</option>
                {assets.map((asset) => (
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
            </form>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[var(--text-muted)]">
                    <th className="py-2">Ticker</th>
                    <th>Classe</th>
                    <th>Quantidade</th>
                    <th>Preço médio</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {portfolio.positions.map((pos) => (
                    <tr key={pos.ticker} className="border-t border-[var(--border-soft)]">
                      <td className="py-3 font-semibold">{pos.ticker}</td>
                      <td>{pos.asset_class}</td>
                      <td>{pos.quantity}</td>
                      <td>{pos.avg_price ? `R$ ${pos.avg_price.toFixed(2)}` : '-'}</td>
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
                  ))}
                </tbody>
              </table>
              {portfolio.positions.length === 0 && (
                <p className="py-4 text-center text-sm text-[var(--text-muted)]">Nenhum ativo ainda. Adicione o primeiro acima.</p>
              )}
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <CompositionCharts positions={portfolio.positions} analysis={analysis} />
        </div>
      </div>
    </div>
  );
}
