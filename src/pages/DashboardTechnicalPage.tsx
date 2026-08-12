import { Info } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card } from '../components/UI';
import { usePortfolios } from '../context/PortfoliosContext';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, PolarAngleAxis, PolarGrid, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { areaSeries, lineSeries, pieSeries, radarSeries } from '../data/mocks';
import { getActivePortfolioSelectionLabel, mapAssetClassToLabel } from '../utils/portfolios';

const colors = ['#684CF2', '#DF50F2', '#941289', '#A896FF', '#B133A3'];

function chartInfo(text: string) {
  return (
    <details className="group relative">
      <summary className="cursor-pointer list-none rounded-full p-1 text-[var(--text-muted)] hover:bg-[rgba(0,0,0,0.05)]">
        <Info size={15} />
      </summary>
      <div className="absolute right-0 z-20 mt-2 w-72 rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3 text-xs leading-5 text-[var(--text-muted)] shadow-[var(--shadow-card)]">
        {text}
      </div>
    </details>
  );
}

export function DashboardTechnicalPage() {
  const { selectedPortfolios, activePortfolio, isAllPortfoliosSelected } = usePortfolios();
  const selectedPositions = selectedPortfolios.flatMap((portfolio) => portfolio.positions);
  const classDistribution = (() => {
    const totals = new Map<string, number>();
    for (const pos of selectedPositions) {
      const label = mapAssetClassToLabel(pos.asset_class);
      totals.set(label, (totals.get(label) ?? 0) + pos.quantity);
    }
    return Array.from(totals.entries()).map(([name, value]) => ({ name, value }));
  })();

  const compositionData = (() => {
    const totals = new Map<string, number>();
    for (const pos of selectedPositions) {
      totals.set(pos.ticker, (totals.get(pos.ticker) ?? 0) + pos.quantity);
    }
    return Array.from(totals.entries()).map(([name, value]) => ({ name, value }));
  })();

  const factor = 1;
  const lineData = lineSeries.map((point) => ({ ...point, value: Number((point.value * factor).toFixed(2)) }));
  const areaData = areaSeries.map((point) => ({ ...point, gain: Number((point.gain * factor).toFixed(2)) }));
  const radarData = radarSeries;

  const metrics = [
    {
      label: 'Carteiras analisadas',
      value: String(selectedPortfolios.length),
      variation: isAllPortfoliosSelected ? 'Visão geral' : 'Seleção ativa',
    },
    {
      label: 'Ativos monitorados',
      value: String(selectedPositions.length),
      variation: 'Posições na carteira',
    },
    {
      label: 'Total de unidades',
      value: selectedPositions.reduce((s, p) => s + p.quantity, 0).toFixed(1),
      variation: 'Soma de posições',
    },
    {
      label: 'Classes distintas',
      value: String(new Set(selectedPositions.map((p) => p.asset_class)).size),
      variation: 'Diversificação',
    },
  ];

  const pieData = compositionData.length ? compositionData : pieSeries;
  const barData = classDistribution.length ? classDistribution : [];

  return (
    <div className="space-y-5">
      <section className="rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(61,77,156,0.1)_0%,rgba(255,255,255,0.95)_60%,rgba(225,94,242,0.08)_100%)] p-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">Painel técnico</p>
            <h2 className="mt-2 text-3xl font-bold">Análises mais detalhadas para leitura profissional</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Compare exposição, tendência simulada e perfil consolidado das carteiras.
            </p>
            <p className="mt-3 text-sm font-semibold text-[var(--brand)]">
              Analisando agora: {getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected)}
            </p>
          </div>
          <Link to="/" className="rounded-2xl border border-[var(--border-soft)] bg-white px-4 py-2.5 text-sm font-semibold text-[var(--text-main)]">
            Voltar para visão simples
          </Link>
        </div>
      </section>

      <div>
        <h3 className="text-2xl font-bold">Comparativos e tendências</h3>
        <p className="text-sm text-[var(--text-muted)]">
          {isAllPortfoliosSelected ? 'Leitura consolidada das carteiras.' : 'Leitura técnica aplicada à seleção atual.'}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <Card key={metric.label}>
            <p className="text-sm text-[var(--text-muted)]">{metric.label}</p>
            <p className="mt-1 text-2xl font-bold">{metric.value}</p>
            <p className="mt-2 text-xs font-semibold text-[var(--brand)]">{metric.variation}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Evolução simulada da carteira" right={chartInfo('Tendência acumulada ao longo dos meses.')}>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={lineData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(37,37,37,0.12)" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#684CF2" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Distribuição por categoria" right={chartInfo('Exposição percentual em cada classe.')}>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(37,37,37,0.12)" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#DF50F2" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Composição por ativo" right={chartInfo('Fatia representa um ativo.')}>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={90}>
                  {pieData.map((_, index) => (
                    <Cell key={index} fill={colors[index % colors.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Tendência semanal" right={chartInfo('Área acima de zero indica ganho simulado.')}>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={areaData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(37,37,37,0.12)" />
                <XAxis dataKey="week" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="gain" stroke="#DF50F2" fill="#DF50F2" fillOpacity={0.25} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card title="Comparação da carteira" right={chartInfo('Compara carteira com benchmark.')}>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" />
              <Radar dataKey="carteira" fill="#684CF2" fillOpacity={0.4} stroke="#684CF2" />
              <Radar dataKey="benchmark" fill="#DF50F2" fillOpacity={0.22} stroke="#DF50F2" />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
