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
  if (score >= 0.7) return { label: 'Saudável', color: 'text-green-600 bg-green-50' };
  if (score >= 0.4) return { label: 'Atenção', color: 'text-amber-600 bg-amber-50' };
  return { label: 'Crítico', color: 'text-red-600 bg-red-50' };
}

export function PortfolioOpinion({ portfolioId }: { portfolioId: string | undefined }) {
  const [data, setData] = useState<OpinionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!portfolioId) return;
    setLoading(true);
    setError(null);
    api.get<OpinionData>(`/models/opinion/${portfolioId}`)
      .then(setData)
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Erro ao carregar opinião');
        setData(null);
      })
      .finally(() => setLoading(false));
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
      <div className="mt-1 h-2 w-full rounded-full bg-gray-200">
        <div
          className="h-full rounded-full bg-[var(--brand)] transition-all"
          style={{ width: `${pctValue}%` }}
        />
      </div>
    </div>
  );
}
