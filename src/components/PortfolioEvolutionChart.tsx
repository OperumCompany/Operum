import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, TrendingUp } from 'lucide-react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { PortfolioHistoryPoint, PortfolioHistoryResponse } from '../types';
import api from '../utils/api';
import { Card, Select } from './UI';

const PERIODS = [
  { value: '1m', label: '1 mês' },
  { value: '6m', label: '6 meses' },
  { value: '1y', label: '1 ano' },
  { value: 'max', label: 'Máximo' },
] as const;

function money(value: number | null | undefined, currency: string) {
  if (value == null) return 'Indisponível';
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency }).format(value);
}

export function PortfolioEvolutionChart({
  portfolioId,
  currency,
  refreshKey = 0,
  defaultPeriod = '6m',
}: {
  portfolioId: string;
  currency: string;
  refreshKey?: number;
  defaultPeriod?: '6m' | '1y';
}) {
  const [period, setPeriod] = useState<PortfolioHistoryResponse['period']>(defaultPeriod);
  const [ticker, setTicker] = useState('');
  const [data, setData] = useState<PortfolioHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setPeriod(defaultPeriod);
    setTicker('');
  }, [defaultPeriod, portfolioId]);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ period });
    if (ticker) params.set('ticker', ticker);
    setLoading(true);
    setError('');
    api.get<PortfolioHistoryResponse>(`/portfolios/${portfolioId}/history?${params.toString()}`)
      .then((result) => {
        if (cancelled) return;
        setData(result);
      })
      .catch((reason) => {
        if (cancelled) return;
        setData(null);
        setError(reason instanceof Error ? reason.message : 'Não foi possível carregar a evolução.');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [period, portfolioId, refreshKey, ticker]);

  const chartData = useMemo(() => (data?.points ?? []).map((point) => ({
    ...point,
    label: new Date(`${point.date}T00:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }),
  })), [data]);

  return (
    <Card
      className="portfolio-evolution print-keep"
      title="Evolução da carteira"
      right={<TrendingUp size={18} className="text-[var(--brand)]" />}
    >
      <div className="portfolio-evolution-controls no-print mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Select value={ticker} onChange={(event) => setTicker(event.target.value)} className="md:max-w-xs">
          <option value="">Carteira completa</option>
          {(data?.available_tickers ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
        </Select>
        <div className="flex flex-wrap gap-2" aria-label="Período do gráfico">
          {PERIODS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setPeriod(option.value)}
              className={`min-h-10 rounded-full px-4 text-xs font-semibold transition ${period === option.value ? 'bg-[#684cf2] text-white' : 'border border-[var(--border-soft)] bg-[var(--bg-surface-muted)] text-[var(--text-main)]'}`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="flex h-72 items-center justify-center text-sm text-[var(--text-muted)]">Carregando evolução...</div>}
      {!loading && error && <div className="flex h-56 items-center justify-center text-center text-sm text-[var(--danger-text)]">{error}</div>}
      {!loading && !error && chartData.length > 0 && (
        <div className="portfolio-evolution-chart h-[340px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid stroke="var(--border-soft)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={28} />
              <YAxis tickLine={false} axisLine={false} width={72} tickFormatter={(value) => new Intl.NumberFormat('pt-BR', { notation: 'compact' }).format(Number(value))} />
              <Tooltip
                content={({ active, payload }) => {
                  const point = payload?.[0]?.payload as (PortfolioHistoryPoint & { label: string }) | undefined;
                  if (!active || !point) return null;
                  return (
                    <div className="rounded-xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3 text-xs shadow-[var(--shadow-float)]">
                      <p className="font-semibold">{new Date(`${point.date}T00:00:00`).toLocaleDateString('pt-BR')}</p>
                      <p className="mt-2 text-[var(--brand)]">Valor: {money(point.market_value, currency)}</p>
                      <p className="mt-1 text-[var(--accent)]">Investido: {money(point.invested_value, currency)}</p>
                      {point.quantity != null && <p className="mt-1 text-[var(--text-muted)]">Quantidade: {point.quantity.toLocaleString('pt-BR')}</p>}
                      {point.contribution_quantity !== 0 && <p className="mt-1 text-[var(--text-muted)]">Movimentação: {point.contribution_quantity.toLocaleString('pt-BR')} un. · {money(point.contribution_value, currency)}</p>}
                    </div>
                  );
                }}
              />
              <Legend />
              <Line type="monotone" dataKey="market_value" name="Valor de mercado" stroke="#684CF2" strokeWidth={3} dot={false} connectNulls />
              <Line type="monotone" dataKey="invested_value" name="Total investido" stroke="#DF50F2" strokeWidth={2} strokeDasharray="7 5" dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {!loading && !error && chartData.length === 0 && <div className="flex h-56 items-center justify-center text-sm text-[var(--text-muted)]">Adicione um ativo para iniciar o histórico.</div>}
      {!!data?.warnings.length && (
        <div className="mt-4 space-y-2">
          {data.warnings.map((warning) => <p key={warning} className="flex items-start gap-2 text-xs text-[var(--text-muted)]"><AlertCircle size={14} className="mt-0.5 shrink-0" />{warning}</p>)}
        </div>
      )}
    </Card>
  );
}
