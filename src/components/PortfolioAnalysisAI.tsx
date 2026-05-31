import { useState } from 'react';
import { Button, Card } from './UI';
import api from '../utils/api';
import type { PortfolioOpinion } from '../types';

function pct(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}

function scoreLabel(score: number): { label: string; color: string } {
  if (score >= 0.7) return { label: 'Saudavel', color: '#22c55e' };
  if (score >= 0.4) return { label: 'Atencao', color: '#eab308' };
  return { label: 'Critico', color: '#ef4444' };
}

function ComponentBar({ label, value, invert }: { label: string; value: number; invert?: boolean }) {
  const displayValue = invert ? 1 - value : value;
  return (
    <div className="flex items-center gap-3">
      <span className="w-36 text-sm text-[var(--text-muted)]">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--bg-surface-strong)]">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${displayValue * 100}%`, backgroundColor: displayValue >= 0.6 ? '#22c55e' : displayValue >= 0.3 ? '#eab308' : '#ef4444' }}
        />
      </div>
      <span className="w-12 text-right text-sm font-medium">{pct(displayValue)}</span>
    </div>
  );
}

export function PortfolioAnalysisAI({ portfolioId }: { portfolioId: string }) {
  const [data, setData] = useState<PortfolioOpinion | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadOpinion() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<PortfolioOpinion>(`/models/opinion/${portfolioId}`);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao gerar analise');
    } finally {
      setLoading(false);
    }
  }

  const sl = data ? scoreLabel(data.score) : null;

  return (
    <Card title="Analise da Carteira">
      {!data && !loading && !error && (
        <div className="flex flex-col items-center gap-3 py-4">
          <p className="text-sm text-[var(--text-muted)]">
            Gere uma analise detalhada com base nos ativos, noticias e indicadores de risco.
          </p>
          <Button type="button" onClick={loadOpinion}>
            Gerar analise por IA
          </Button>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-3 py-4">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--brand)] border-t-transparent" />
          <p className="text-sm text-[var(--text-muted)]">Gerando analise...</p>
        </div>
      )}

      {error && (
        <div className="space-y-3 py-2">
          <p className="text-sm text-[var(--danger-text)]">{error}</p>
          <Button type="button" onClick={loadOpinion}>Tentar novamente</Button>
        </div>
      )}

      {data && sl && (
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div
              className="flex h-16 w-16 items-center justify-center rounded-full text-lg font-bold text-white"
              style={{ backgroundColor: sl.color }}
            >
              {pct(data.score)}
            </div>
            <div>
              <p className="text-lg font-bold" style={{ color: sl.color }}>{sl.label}</p>
              <p className="text-xs text-[var(--text-muted)]">Score consolidado da carteira</p>
            </div>
          </div>

          <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
            <p className="text-sm font-semibold text-[var(--text-main)]">{data.headline}</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{data.composition_summary}</p>
            <div className="mt-3 rounded-2xl bg-white/80 p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Nota geral da composicao</p>
              <p className="mt-1 text-lg font-bold text-[var(--text-main)]">{data.composition_grade}</p>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Componentes</p>
            <ComponentBar label="Diversificacao" value={data.components.diversification} />
            <ComponentBar label="Risco correlacao" value={data.components.correlation_risk} invert />
            <ComponentBar label="Impacto noticias" value={data.components.news_impact} invert />
            <ComponentBar label="Sensibilidade macro" value={data.components.macro_sensitivity} invert />
            <ComponentBar label="Risco forecast" value={data.components.forecast_risk} invert />
          </div>

          {!!data.strengths.length && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Pontos fortes</p>
              {data.strengths.map((item) => (
                <p key={item} className="text-sm leading-relaxed text-[var(--text-main)]">{item}</p>
              ))}
            </div>
          )}

          {!!data.overlaps.length && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Sobreposicoes e riscos</p>
              {data.overlaps.map((item) => (
                <p key={item} className="text-sm leading-relaxed text-[var(--text-main)]">{item}</p>
              ))}
            </div>
          )}

          {!!data.block_reviews.length && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Avaliacao por blocos</p>
              {data.block_reviews.map((review) => (
                <div key={review.title} className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
                  <p className="text-sm font-semibold text-[var(--text-main)]">{review.title}</p>
                  <p className="mt-1 text-sm leading-relaxed text-[var(--text-main)]">{review.assessment}</p>
                  <p className="mt-2 text-xs leading-relaxed text-[var(--text-muted)]">{review.highlights}</p>
                </div>
              ))}
            </div>
          )}

          <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Diagnostico final</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{data.final_diagnosis}</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{data.conclusion}</p>
          </div>

          {!!data.sources.length && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Fontes relacionadas</p>
              {data.sources.map((source) => (
                <a
                  key={source.id}
                  href={source.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="block rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3 transition hover:border-[var(--brand)]"
                >
                  <p className="text-sm font-semibold text-[var(--text-main)]">{source.title}</p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">{source.source_name}</p>
                </a>
              ))}
            </div>
          )}

          <Button type="button" variant="ghost" onClick={loadOpinion}>
            Regenerar analise
          </Button>
        </div>
      )}
    </Card>
  );
}
