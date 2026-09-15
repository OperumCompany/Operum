import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Blocks, LoaderCircle } from 'lucide-react';
import { ResponsiveContainer, Tooltip, Treemap } from 'recharts';
import type { Portfolio, PortfolioPricePosition, PortfolioPricesResponse } from '../types';
import api from '../utils/api';

const CLASS_COLORS: Record<string, string> = {
  BR_STOCK: '#684CF2',
  FII: '#DF50F2',
  US_STOCK: '#3D4D9C',
  BDR: '#A896FF',
  CRYPTO: '#941289',
};

const CLASS_LABELS: Record<string, string> = {
  BR_STOCK: 'Ações brasileiras',
  FII: 'Fundos imobiliários',
  US_STOCK: 'Exterior e BDRs',
  BDR: 'BDRs',
  CRYPTO: 'Criptoativos',
};

type AllocationItem = {
  name: string;
  size: number;
  assetClass: string;
  value: number;
  percent: number;
  fill: string;
};

type TreemapContentProps = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  percent?: number;
  fill?: string;
};

function AllocationTile({ x = 0, y = 0, width = 0, height = 0, name = '', percent = 0, fill = '#684CF2' }: TreemapContentProps) {
  const showTicker = width >= 62 && height >= 38;
  const showPercent = width >= 90 && height >= 58;
  return (
    <g>
      <rect x={x + 2} y={y + 2} width={Math.max(0, width - 4)} height={Math.max(0, height - 4)} rx={12} fill={fill} opacity={0.92} />
      {showTicker && <text x={x + 12} y={y + 24} fill="#fff" fontSize={12} fontWeight={700}>{name}</text>}
      {showPercent && <text x={x + 12} y={y + 43} fill="rgba(255,255,255,.82)" fontSize={11}>{percent.toFixed(1)}%</text>}
    </g>
  );
}

function money(value: number, currency: string | null) {
  if (!currency) return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 }).format(value);
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency }).format(value);
}

function PortfolioAllocationMapGroup({ portfolios }: { portfolios: Portfolio[] }) {
  const [data, setData] = useState<PortfolioPricesResponse | null>(null);
  const [missingQuotes, setMissingQuotes] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!portfolios.length) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    Promise.all(portfolios.map((portfolio) => api.get<PortfolioPricesResponse>(`/portfolios/${portfolio.id}/prices`)))
      .then((responses) => {
        if (cancelled) return;
        const byAsset = new Map<string, PortfolioPricePosition>();
        let unavailable = 0;
        for (const response of responses) {
          for (const position of response.positions) {
            if (position.total_value == null) unavailable += 1;
            const key = `${position.asset_class}:${position.ticker}`;
            const current = byAsset.get(key);
            if (!current) {
              byAsset.set(key, { ...position });
              continue;
            }
            current.quantity += position.quantity;
            current.total_value = current.total_value == null && position.total_value == null
              ? null
              : (current.total_value ?? 0) + (position.total_value ?? 0);
          }
        }
        const positions = Array.from(byAsset.values());
        const totalValue = positions.reduce((sum, position) => sum + (position.total_value ?? 0), 0);
        for (const position of positions) position.weight_pct = position.total_value != null && totalValue ? position.total_value / totalValue * 100 : null;
        setMissingQuotes(unavailable);
        setData({ portfolio_id: portfolios.map((item) => item.id).join(','), portfolio_name: portfolios.length === 1 ? portfolios[0].name : 'Todas as carteiras', total_value: totalValue || null, total_unrealized_pnl: null, positions });
      })
      .catch((reason) => {
        if (!cancelled) {
          setData(null);
          setError(reason instanceof Error ? reason.message : 'Não foi possível carregar a alocação.');
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [portfolios]);

  const allocation = useMemo<AllocationItem[]>(() => (data?.positions ?? [])
    .filter((item) => item.total_value != null && item.total_value > 0)
    .map((item) => ({
      name: item.ticker,
      size: item.total_value as number,
      assetClass: item.asset_class === 'US_STOCK' && /\d{2}$/.test(item.ticker) ? 'BDR' : item.asset_class,
      value: item.total_value as number,
      percent: item.weight_pct ?? 0,
      fill: CLASS_COLORS[item.asset_class] ?? '#8B7CF6',
    }))
    .sort((a, b) => b.value - a.value), [data]);

  const displayCurrency = portfolios[0]?.base_currency ?? 'BRL';
  const classSummary = useMemo(() => {
    const totals = new Map<string, number>();
    for (const item of allocation) totals.set(item.assetClass, (totals.get(item.assetClass) ?? 0) + item.value);
    const total = allocation.reduce((sum, item) => sum + item.value, 0);
    return Array.from(totals.entries()).map(([key, value]) => ({ key, value, percent: total ? value / total * 100 : 0 })).sort((a, b) => b.value - a.value);
  }, [allocation]);

  if (!portfolios.length) return <p className="py-10 text-sm text-[var(--text-muted)]">Nenhuma carteira disponível para visualizar a alocação.</p>;
  if (loading) return <div className="flex h-72 items-center justify-center gap-2 text-sm text-[var(--text-muted)]"><LoaderCircle size={18} className="animate-spin" />Carregando alocação...</div>;
  if (error) return <div className="flex min-h-48 items-center gap-2 text-sm text-[var(--danger-text)]"><AlertCircle size={18} />{error}</div>;
  if (!allocation.length) return <div className="flex min-h-48 flex-col items-center justify-center gap-3 text-center"><Blocks className="text-[var(--brand)]" /><p className="text-sm text-[var(--text-muted)]">Ainda não há posições com cotação para montar o mapa.</p></div>;

  return (
    <div className="portfolio-allocation-map">
      <div className="h-[300px] min-h-[260px] w-full sm:h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <Treemap data={allocation} dataKey="size" nameKey="name" stroke="transparent" content={<AllocationTile />} isAnimationActive={false}>
            <Tooltip content={({ active, payload }) => {
              const item = payload?.[0]?.payload as AllocationItem | undefined;
              if (!active || !item) return null;
              return <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3 text-xs shadow-[var(--shadow-float)]"><p className="font-bold text-[var(--text-main)]">{item.name}</p><p className="mt-1 text-[var(--text-muted)]">{CLASS_LABELS[item.assetClass] ?? item.assetClass}</p><p className="mt-2 font-semibold text-[var(--brand)]">{money(item.value, displayCurrency)} · {item.percent.toFixed(1)}%</p></div>;
            }} />
          </Treemap>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {classSummary.map((item) => <div key={item.key} className="flex items-center justify-between rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-muted)] px-3 py-2 text-xs"><span className="flex items-center gap-2 font-semibold text-[var(--text-main)]"><span className="h-2.5 w-2.5 rounded-full" style={{ background: CLASS_COLORS[item.key] ?? '#8B7CF6' }} />{CLASS_LABELS[item.key] ?? item.key}</span><span className="text-[var(--text-muted)]">{item.percent.toFixed(1)}%</span></div>)}
      </div>
      {missingQuotes > 0 && <p className="mt-3 flex items-start gap-2 text-xs text-[var(--text-muted)]"><AlertCircle size={14} className="mt-0.5 shrink-0" />{missingQuotes} ativo(s) sem cotação não participam do cálculo.</p>}
    </div>
  );
}

export function PortfolioAllocationMap({ portfolios }: { portfolios: Portfolio[] }) {
  const groups = useMemo(() => {
    const grouped = new Map<string, Portfolio[]>();
    for (const portfolio of portfolios) {
      const currency = portfolio.base_currency || 'BRL';
      grouped.set(currency, [...(grouped.get(currency) ?? []), portfolio]);
    }
    return Array.from(grouped.entries());
  }, [portfolios]);

  if (groups.length <= 1) return <PortfolioAllocationMapGroup portfolios={portfolios} />;
  return (
    <div className="space-y-6">
      {groups.map(([currency, currencyPortfolios]) => (
        <section key={currency} className="rounded-[24px] border border-[var(--border-soft)] bg-[var(--bg-surface-muted)] p-3 sm:p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Moeda-base {currency}</p>
          <PortfolioAllocationMapGroup portfolios={currencyPortfolios} />
        </section>
      ))}
    </div>
  );
}
