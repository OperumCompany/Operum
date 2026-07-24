import { useRef, useState } from 'react';
import { Button, Card } from './UI';
import api from '../utils/api';
import type { PortfolioOpinion } from '../types';

function pct(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}

function pctPoint(v: number): string {
  return `${v.toFixed(1)}%`;
}

function scoreLabel(score: number): { label: string; color: string } {
  if (score >= 0.7) return { label: 'Saudável', color: '#22c55e' };
  if (score >= 0.4) return { label: 'Atenção', color: '#eab308' };
  return { label: 'Crítico', color: '#ef4444' };
}

function statusStyle(status: string): string {
  if (status === 'saudavel') return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  if (status === 'critico') return 'border-red-200 bg-red-50 text-red-800';
  if (status === 'atencao') return 'border-amber-200 bg-amber-50 text-amber-800';
  return 'border-slate-200 bg-slate-50 text-slate-700';
}

function statusLabel(status: string): string {
  if (status === 'saudavel') return 'Saudável';
  if (status === 'critico') return 'Crítico';
  if (status === 'atencao') return 'Atenção';
  return 'Informativo';
}

const HORIZONS = [
  { key: '1m', label: '1 mês' },
  { key: '2m', label: '2 meses' },
  { key: '3m', label: '3 meses' },
] as const;

type AnalysisHorizon = (typeof HORIZONS)[number]['key'];
type OpinionCache = Partial<Record<AnalysisHorizon, PortfolioOpinion>>;
type OpinionRequests = Partial<Record<AnalysisHorizon, Promise<PortfolioOpinion>>>;

const PREFETCH_HORIZONS: AnalysisHorizon[] = ['2m', '1m'];

export function PortfolioAnalysisAI({ portfolioId }: { portfolioId: string }) {
  const [data, setData] = useState<PortfolioOpinion | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [analysisHorizon, setAnalysisHorizon] = useState<AnalysisHorizon>('3m');
  const cacheRef = useRef<OpinionCache>({});
  const inFlightRef = useRef<OpinionRequests>({});

  async function fetchOpinion(nextHorizon: AnalysisHorizon) {
    const cached = cacheRef.current[nextHorizon];
    if (cached) return cached;

    const inFlight = inFlightRef.current[nextHorizon];
    if (inFlight) return inFlight;

    const request = api
      .get<PortfolioOpinion>(`/models/opinion/${portfolioId}?analysis_horizon=${nextHorizon}`)
      .then((result) => {
        cacheRef.current[nextHorizon] = result;
        return result;
      })
      .finally(() => {
        delete inFlightRef.current[nextHorizon];
      });

    inFlightRef.current[nextHorizon] = request;
    return request;
  }

  async function prefetchOpinions(baseHorizon: AnalysisHorizon) {
    for (const horizon of PREFETCH_HORIZONS) {
      if (horizon === baseHorizon || cacheRef.current[horizon]) {
        continue;
      }
      try {
        await fetchOpinion(horizon);
      } catch {
        // Background prefetch must not affect the visible analysis.
      }
    }
  }

  async function loadOpinion(nextHorizon = analysisHorizon, options: { prefetch?: boolean } = { prefetch: true }) {
    const cached = cacheRef.current[nextHorizon];
    if (cached) {
      setData(cached);
      setExpandedSources({});
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await fetchOpinion(nextHorizon);
      setData(result);
      setExpandedSources({});
      if (options.prefetch) {
        void prefetchOpinions(nextHorizon);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao gerar análise');
    } finally {
      setLoading(false);
    }
  }

  async function changeHorizon(nextHorizon: AnalysisHorizon) {
    setAnalysisHorizon(nextHorizon);
    if (data || loading) {
      await loadOpinion(nextHorizon, { prefetch: false });
    }
  }

  function toggleSourceGroup(sourceName: string) {
    setExpandedSources((prev) => ({
      ...prev,
      [sourceName]: !prev[sourceName],
    }));
  }

  const sl = data ? scoreLabel(data.score) : null;
  const cd = data?.composition_diagnosis;

  return (
    <Card title="Análise da Carteira">
      {!data && !loading && !error && (
        <div className="flex flex-col items-center gap-3 py-4">
          <p className="text-sm text-[var(--text-muted)]">
            Gere uma análise detalhada com base nos ativos, notícias e indicadores de risco.
          </p>
          <Button type="button" onClick={() => loadOpinion()}>
            Gerar análise por IA
          </Button>
        </div>
      )}

      {(loading || data) && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Janela</span>
          {HORIZONS.map((horizon) => (
            <button
              key={horizon.key}
              type="button"
              onClick={() => changeHorizon(horizon.key)}
              className={`rounded-full px-3 py-2 text-xs font-semibold transition ${
                analysisHorizon === horizon.key
                  ? 'bg-[var(--brand)] text-white'
                  : 'border border-[var(--border-soft)] bg-white text-[var(--text-main)] hover:border-[var(--brand)]'
              }`}
            >
              {horizon.label}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-3 py-4">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--brand)] border-t-transparent" />
          <p className="text-sm text-[var(--text-muted)]">Gerando análise...</p>
        </div>
      )}

      {error && (
        <div className="space-y-3 py-2">
          <p className="text-sm text-[var(--danger-text)]">{error}</p>
          <Button type="button" onClick={() => loadOpinion()}>
            Tentar novamente
          </Button>
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
              <p className="text-lg font-bold" style={{ color: sl.color }}>
                {sl.label}
              </p>
              <p className="text-xs text-[var(--text-muted)]">Score consolidado da carteira</p>
            </div>
          </div>

          <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
            <p className="text-sm font-semibold text-[var(--text-main)]">{data.headline}</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{data.composition_summary}</p>
            <div className="mt-3 rounded-2xl bg-white/80 p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Nota geral da composição</p>
              <p className="mt-1 text-lg font-bold text-[var(--text-main)]">{data.composition_grade}</p>
            </div>
          </div>

          {cd && (
            <div className="space-y-4 rounded-3xl border border-[var(--border-soft)] bg-white p-4 shadow-sm">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Diagnóstico de composição</p>
                  <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{cd.summary}</p>
                </div>
                <div className={`w-fit rounded-full border px-3 py-1 text-xs font-bold ${statusStyle(cd.overall_status)}`}>
                  {statusLabel(cd.overall_status)} · {cd.overall_score}/100
                </div>
              </div>

              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3">
                  <p className="text-xs text-[var(--text-muted)]">Ativos</p>
                  <p className="mt-1 text-lg font-bold">{cd.metrics.total_assets}</p>
                  <p className="text-xs text-[var(--text-muted)]">{cd.metrics.direct_equity_count} ação(ões) direta(s)</p>
                </div>
                <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3">
                  <p className="text-xs text-[var(--text-muted)]">Maior posição</p>
                  <p className="mt-1 text-lg font-bold">{cd.metrics.top_position.ticker ?? '-'}</p>
                  <p className="text-xs text-[var(--text-muted)]">{pctPoint(cd.metrics.top_position.weight_pct)} da carteira</p>
                </div>
                <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3">
                  <p className="text-xs text-[var(--text-muted)]">Top 3 posições</p>
                  <p className="mt-1 text-lg font-bold">{pctPoint(cd.metrics.top3_weight_pct)}</p>
                  <p className="text-xs text-[var(--text-muted)]">peso combinado</p>
                </div>
                <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3">
                  <p className="text-xs text-[var(--text-muted)]">Exterior</p>
                  <p className="mt-1 text-lg font-bold">{pctPoint(cd.metrics.international_weight_pct)}</p>
                  <p className="text-xs text-[var(--text-muted)]">{cd.metrics.class_count} classe(s), {cd.metrics.sector_count} setor(es)</p>
                </div>
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Verificações principais</p>
                  {cd.checks.slice(0, 5).map((check) => (
                    <div key={check.id} className={`rounded-2xl border p-3 ${statusStyle(check.status)}`}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold">{check.label}</p>
                        <p className="text-xs font-bold">{statusLabel(check.status)}</p>
                      </div>
                      <p className="mt-1 text-xs font-medium">{check.value}</p>
                      <p className="mt-1 text-xs leading-relaxed opacity-90">{check.message}</p>
                    </div>
                  ))}
                </div>

                <div className="space-y-3">
                  {!!cd.strengths.length && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Pontos fortes</p>
                      <div className="mt-2 space-y-2">
                        {cd.strengths.slice(0, 4).map((item) => (
                          <p key={item} className="rounded-2xl bg-emerald-50 p-3 text-sm leading-relaxed text-emerald-900">{item}</p>
                        ))}
                      </div>
                    </div>
                  )}
                  {!!cd.weaknesses.length && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Pontos fracos</p>
                      <div className="mt-2 space-y-2">
                        {cd.weaknesses.slice(0, 4).map((item) => (
                          <p key={item} className="rounded-2xl bg-amber-50 p-3 text-sm leading-relaxed text-amber-900">{item}</p>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {!!cd.watch_points.length && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">O que acompanhar</p>
                  <div className="mt-2 grid gap-2 md:grid-cols-2">
                    {cd.watch_points.slice(0, 5).map((item) => (
                      <p key={item} className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3 text-sm leading-relaxed">{item}</p>
                    ))}
                  </div>
                </div>
              )}

              {!!cd.data_quality_warnings.length && (
                <p className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">
                  {cd.data_quality_warnings.join(' ')}
                </p>
              )}
            </div>
          )}

          {!!data.overlaps.length && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Sobreposições e riscos</p>
              {data.overlaps.map((item) => (
                <p key={item} className="text-sm leading-relaxed text-[var(--text-main)]">
                  {item}
                </p>
              ))}
            </div>
          )}

          <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Diagnóstico final</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{data.final_diagnosis}</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--text-main)]">{data.conclusion}</p>
          </div>

          {!!data.source_groups.length && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Fontes relacionadas</p>
              <div className="flex flex-wrap gap-2">
                {data.source_groups.map((group) => (
                  <button
                    key={group.source_name}
                    type="button"
                    onClick={() => toggleSourceGroup(group.source_name)}
                    className="rounded-full border border-[var(--border-soft)] bg-white px-3 py-2 text-xs font-semibold text-[var(--text-main)] transition hover:border-[var(--brand)]"
                  >
                    {group.source_name} ({group.count})
                  </button>
                ))}
              </div>
              <div className="space-y-3">
                {data.source_groups
                  .filter((group) => expandedSources[group.source_name])
                  .map((group) => (
                    <div key={`${group.source_name}-panel`} className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3">
                      <p className="text-sm font-semibold text-[var(--text-main)]">{group.source_name}</p>
                      <div className="mt-3 space-y-2">
                        {group.items.map((item) => (
                          <a
                            key={item.id}
                            href={item.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="block rounded-2xl border border-[var(--border-soft)] bg-white p-3 transition hover:border-[var(--brand)]"
                          >
                            <p className="text-sm font-semibold text-[var(--text-main)]">{item.title}</p>
                            <p className="mt-1 text-xs text-[var(--text-muted)]">{new Date(item.published_at).toLocaleDateString('pt-BR')}</p>
                          </a>
                        ))}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          <Button type="button" variant="ghost" onClick={() => loadOpinion()}>
            Regenerar análise
          </Button>
        </div>
      )}
    </Card>
  );
}
