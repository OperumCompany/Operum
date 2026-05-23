import { useMemo } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Card } from './UI';
import { Position, PortfolioAnalysis } from '../types';

const chartColors = ['#3D4D9C', '#C7559B', '#E15EF2', '#717171', '#A5A5A5', '#5BA3E6', '#F2C94C', '#27AE60'];

function pickColor(index: number): string {
  return chartColors[index % chartColors.length];
}

function buildPieData(positions: Position[], analysis: PortfolioAnalysis | null, mode: 'ticker' | 'class') {
  if (mode === 'ticker') {
    return positions.map((p) => ({
      name: p.ticker,
      value: analysis?.weights?.[p.ticker] != null ? Math.round(analysis.weights[p.ticker] * 10000) : p.quantity,
    }));
  }
  const classMap: Record<string, number> = {};
  if (analysis?.class_weights) {
    for (const [cls, w] of Object.entries(analysis.class_weights)) {
      classMap[cls] = Math.round(w * 10000);
    }
  } else {
    for (const p of positions) {
      classMap[p.asset_class] = (classMap[p.asset_class] ?? 0) + p.quantity;
    }
  }
  return Object.entries(classMap).map(([name, value]) => ({ name, value }));
}

export function CompositionCharts({
  positions,
  analysis,
}: {
  positions: Position[];
  analysis: PortfolioAnalysis | null;
}) {
  const tickerPie = useMemo(() => buildPieData(positions, analysis, 'ticker'), [positions, analysis]);
  const classPie = useMemo(() => buildPieData(positions, analysis, 'class'), [positions, analysis]);

  if (!positions.length) {
    return (
      <Card title="Composição">
        <p className="text-sm text-[var(--text-muted)]">Nenhum ativo na carteira.</p>
      </Card>
    );
  }

  return (
    <Card title="Composição">
      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-center text-sm font-semibold text-[var(--text-muted)]">Por ativo</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={tickerPie} dataKey="value" nameKey="name" outerRadius={70}>
                  {tickerPie.map((_, i) => (
                    <Cell key={i} fill={pickColor(i)} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <p className="mb-2 text-center text-sm font-semibold text-[var(--text-muted)]">Por classe</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={classPie} dataKey="value" nameKey="name" outerRadius={70}>
                  {classPie.map((_, i) => (
                    <Cell key={i} fill={pickColor(i + 3)} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <div className="mt-4 space-y-1">
        {positions.map((pos) => (
          <div key={pos.ticker} className="flex justify-between text-sm">
            <span className="text-[var(--text-main)]">{pos.ticker}</span>
            <span className="text-[var(--text-muted)]">
              {pos.quantity} un{pos.avg_price ? ` · R$ ${pos.avg_price.toFixed(2)}` : ''}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
