import { PortfolioAnalysis } from '../types';
import { Card } from './UI';

function fmt(v: number | null, decimals = 2): string {
  if (v === null || v === undefined) return '-';
  return v.toFixed(decimals);
}

function pct(v: number | null): string {
  if (v === null || v === undefined) return '-';
  return `${(v * 100).toFixed(2)}%`;
}

function getConcentrationColor(label: string): string {
  if (label.includes('Alta')) return 'text-red-600';
  if (label.includes('moderada')) return 'text-amber-600';
  return 'text-green-600';
}

export function PortfolioMetrics({ analysis }: { analysis: PortfolioAnalysis | null }) {
  if (!analysis || analysis.num_assets === 0) {
    return (
      <Card title="Análise da carteira">
        <p className="text-sm text-[var(--text-muted)]">
          Adicione ativos para ver métricas de risco e diversificação.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Análise da carteira">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <MetricBox label="Concentração" value={analysis.concentration_label} valueClass={getConcentrationColor(analysis.concentration_label)} />
        <MetricBox label="Índice de concentração" value={fmt(analysis.concentration, 4)} />
        <MetricBox label="Volatilidade (anual)" value={pct(analysis.volatility)} />
        <MetricBox label="VaR (95%)" value={pct(analysis.var_95)} />
        <MetricBox label="CVaR (95%)" value={pct(analysis.cvar_95)} />
        <MetricBox label="Beta" value={fmt(analysis.beta)} />
        <MetricBox label="Retorno médio" value={pct(analysis.portfolio_return)} />
        <MetricBox label="Ativos" value={String(analysis.num_assets)} />
        <MetricBox label="Classes" value={String(analysis.num_classes)} />
      </div>
      {analysis.class_weights && Object.keys(analysis.class_weights).length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-sm font-semibold text-[var(--text-muted)]">Alocação por classe</p>
          <div className="space-y-1">
            {Object.entries(analysis.class_weights).map(([cls, w]) => (
              <div key={cls} className="flex items-center justify-between text-sm">
                <span>{cls}</span>
                <span className="font-semibold">{(w * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function MetricBox({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3">
      <p className="text-xs text-[var(--text-muted)]">{label}</p>
      <p className={`mt-1 text-base font-bold ${valueClass ?? 'text-[var(--text-main)]'}`}>{value}</p>
    </div>
  );
}
