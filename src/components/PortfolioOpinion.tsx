import { useState, useEffect } from 'react';
import { Lightbulb } from 'lucide-react';
import { Card } from './UI';
import api from '../utils/api';

type OpinionData = {
  score: number;
  components: {
    diversification: number;
    correlation_risk: number;
    news_impact: number;
    macro_sensitivity: number;
    forecast_risk: number;
  };
  opinion: string;
  portfolio_id: string;
};

function scoreLabel(score: number): { label: string; color: string } {
  if (score >= 0.7) return { label: 'Saudável', color: 'text-[var(--success-text)] bg-[var(--success-soft)]' };
  if (score >= 0.4) return { label: 'Atenção', color: 'text-[var(--accent-strong)] bg-[var(--accent-soft)]' };
  return { label: 'Crítico', color: 'text-[var(--danger-text)] bg-[var(--danger-soft)]' };
}

export function PortfolioOpinion({ portfolioId }: { portfolioId: string | undefined }) {
  const [data, setData] = useState<OpinionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!portfolioId) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);
    api.get<OpinionData>(`/models/opinion/${portfolioId}`)
      .then((result) => { if (!cancelled) setData(result); })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Erro ao carregar opinião');
        setData(null);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [portfolioId]);

  if (!portfolioId) return null;

  return (
    <Card title="Opinião da carteira" right={<Lightbulb size={18} className="text-[var(--brand)]" />}>
      {loading && <p className="text-sm text-[var(--text-muted)]">Gerando opinião...</p>}
      {error && <p className="text-sm text-[var(--danger-text)]">{error}</p>}
      {data && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${scoreLabel(data.score).color}`}>
              {scoreLabel(data.score).label}
            </span>
            <span className="text-2xl font-bold text-[var(--text-main)]">{(data.score * 100).toFixed(0)}%</span>
          </div>

          <p className="text-sm leading-6 text-[var(--text-main)]">{data.opinion}</p>

          <div className="space-y-2">
            <p className="text-xs font-semibold text-[var(--text-muted)]">Componentes</p>
            <div className="grid grid-cols-2 gap-2">
              <ComponentBar label="Diversificação" value={data.components.diversification} />
              <ComponentBar label="Risco correlação" value={1 - data.components.correlation_risk} />
              <ComponentBar label="Impacto notícias" value={1 - data.components.news_impact} />
              <ComponentBar label="Sensibilidade macro" value={1 - data.components.macro_sensitivity} />
              <div className="col-span-2">
                <ComponentBar label="Risco forecast" value={1 - data.components.forecast_risk} />
              </div>
            </div>
          </div>
        </div>
      )}
      {!loading && !error && !data && (
        <p className="text-sm text-[var(--text-muted)]">Selecione uma carteira com ativos para ver a opinião.</p>
      )}
    </Card>
  );
}

function ComponentBar({ label, value }: { label: string; value: number }) {
  const pctValue = Math.max(0, Math.min(100, value * 100));
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-[var(--text-muted)]">{label}</span>
        <span className="font-semibold">{pctValue.toFixed(0)}%</span>
      </div>
      <div className="mt-1 h-2 w-full rounded-full bg-[var(--bg-surface-high)]">
        <div
          className="h-full rounded-full bg-[var(--brand)] transition-all"
          style={{ width: `${pctValue}%` }}
        />
      </div>
    </div>
  );
}
