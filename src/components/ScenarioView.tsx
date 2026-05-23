import { useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card } from './UI';

type Scenario = {
  label: string;
  description: string;
  return_pct: number;
  probability: string;
};

const defaultScenarios: Scenario[] = [
  { label: 'Conservador', description: 'Cenário de juros estáveis e crescimento moderado', return_pct: 1.2, probability: '40%' },
  { label: 'Moderado', description: 'Crescimento consistente com inflação controlada', return_pct: 2.8, probability: '30%' },
  { label: 'Agressivo', description: 'Cenário de otimismo com fluxo externo forte', return_pct: 4.9, probability: '15%' },
  { label: 'Inflação alta', description: 'Pressão inflacionária reduzindo poder de compra', return_pct: -0.7, probability: '10%' },
  { label: 'Juros em queda', description: 'Afrouxamento monetário estimulando risco', return_pct: 3.4, probability: '5%' },
];

function Icon({ value }: { value: number }) {
  if (value > 0) return <TrendingUp size={16} className="text-green-600" />;
  if (value < 0) return <TrendingDown size={16} className="text-red-600" />;
  return <Minus size={16} className="text-gray-400" />;
}

export function ScenarioView({ scenarios }: { scenarios?: Scenario[] }) {
  const data = scenarios ?? defaultScenarios;

  const sorted = useMemo(() => [...data].sort((a, b) => b.return_pct - a.return_pct), [data]);

  return (
    <Card title="Cenários simulados">
      <p className="mb-4 text-sm text-[var(--text-muted)]">
        Projeções ilustrativas baseadas em condições macroeconômicas hipotéticas. Não são recomendações de investimento.
      </p>
      <div className="space-y-3">
        {sorted.map((s) => (
          <div
            key={s.label}
            className="flex items-center gap-3 rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3"
          >
            <Icon value={s.return_pct} />
            <div className="flex-1">
              <p className="text-sm font-semibold">{s.label}</p>
              <p className="text-xs text-[var(--text-muted)]">{s.description}</p>
            </div>
            <div className="text-right">
              <p className={`text-sm font-bold ${s.return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {s.return_pct >= 0 ? '+' : ''}{s.return_pct}%
              </p>
              <p className="text-xs text-[var(--text-muted)]">{s.probability}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
