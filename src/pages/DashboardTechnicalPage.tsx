import { Info } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card } from '../components/UI';
import { usePortfolios } from '../context/PortfoliosContext';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { areaSeries, assetsCatalog, lineSeries, pieSeries, radarSeries } from '../data/mocks';
import { getActivePortfolioSelectionLabel } from '../utils/portfolios';

const colors = ['#3D4D9C', '#C7559B', '#E15EF2', '#717171', '#A5A5A5'];

function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

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
  const selectedAssets = selectedPortfolios.flatMap((portfolio) => portfolio.assets);
  const hasAssets = selectedAssets.length > 0;

  const classDistribution = (() => {
    const totals = new Map<string, number>();

    for (const asset of selectedAssets) {
      const catalog = assetsCatalog.find((item) => item.ticker === asset.ticker);
      const rawClass = catalog?.class ?? 'Outros';
      const key = normalizeText(rawClass).includes('renda')
        ? 'Renda fixa'
        : normalizeText(rawClass).includes('cripto')
          ? 'Cripto'
          : normalizeText(rawClass).includes('fund')
            ? 'Fundos'
            : normalizeText(rawClass).includes('eua')
              ? 'Ações EUA'
              : 'Ações BR';

      totals.set(key, (totals.get(key) ?? 0) + asset.allocation);
    }

    return Array.from(totals.entries()).map(([name, value]) => ({ name, value }));
  })();

  const compositionData = (() => {
    const totals = new Map<string, number>();

    for (const asset of selectedAssets) {
      totals.set(asset.ticker, (totals.get(asset.ticker) ?? 0) + asset.allocation);
    }

    return Array.from(totals.entries()).map(([name, value]) => ({ name, value }));
  })();

  const weightedRisk = (() => {
    if (!selectedAssets.length) return 0;

    const total = selectedAssets.reduce((sum, asset) => sum + asset.allocation, 0);
    if (!total) return 0;

    const weighted = selectedAssets.reduce((sum, asset) => {
      const risk = assetsCatalog.find((item) => item.ticker === asset.ticker)?.risk ?? 3;
      return sum + risk * asset.allocation;
    }, 0);

    return weighted / total;
  })();

  const factor = 1 + (weightedRisk - 3) * 0.025;

  const lineData = hasAssets
    ? lineSeries.map((point) => ({ ...point, value: Number((point.value * factor).toFixed(2)) }))
    : lineSeries;

  const areaData = hasAssets
    ? areaSeries.map((point) => ({ ...point, gain: Number((point.gain * factor).toFixed(2)) }))
    : areaSeries;

  const radarData = hasAssets
    ? radarSeries.map((point) => ({
        ...point,
        carteira: Math.max(10, Math.min(100, Number((point.carteira * factor).toFixed(2)))),
      }))
    : radarSeries;

  const metrics = [
    {
      label: 'Carteiras analisadas',
      value: String(selectedPortfolios.length),
      variation: isAllPortfoliosSelected ? 'Visão geral' : 'Seleção ativa',
    },
    {
      label: 'Ativos monitorados',
      value: String(selectedAssets.length),
      variation: 'Composição observada',
    },
    {
      label: 'Risco médio',
      value: weightedRisk ? weightedRisk.toFixed(2) : '0.00',
      variation: 'Escala de 1 a 5',
    },
    {
      label: 'Alocação total',
      value: `${selectedAssets.reduce((sum, asset) => sum + asset.allocation, 0).toFixed(0)}%`,
      variation: 'Soma dos ativos',
    },
  ];

  const pieData = compositionData.length ? compositionData : pieSeries;
  const barData = classDistribution.length
    ? classDistribution
    : [
        { name: 'Renda fixa', value: 0 },
        { name: 'Ações BR', value: 0 },
        { name: 'Ações EUA', value: 0 },
        { name: 'Fundos', value: 0 },
        { name: 'Cripto', value: 0 },
      ];

  return (
    <div className="space-y-5">
      <section className="rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(61,77,156,0.1)_0%,rgba(255,255,255,0.95)_60%,rgba(225,94,242,0.08)_100%)] p-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">Painel técnico</p>
            <h2 className="mt-2 text-3xl font-bold">Análises mais detalhadas para leitura profissional</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Use este painel para comparar exposição, tendência simulada e perfil consolidado das carteiras em mais profundidade.
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
          {isAllPortfoliosSelected
            ? 'Leitura consolidada das carteiras, ativos e contexto de simulação.'
            : 'Leitura técnica aplicada à seleção atual de carteiras.'}
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
        <Card
          title="Evolução simulada da carteira"
          right={chartInfo('Mostra a tendência acumulada ao longo dos meses. Linha em alta indica valorização no período; em queda, perda de valor.')}
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={lineData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(37,37,37,0.12)" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#3D4D9C" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title="Distribuição por categoria"
          right={chartInfo('Barras maiores significam maior exposição percentual em cada classe de investimento no consolidado das carteiras.')}
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(37,37,37,0.12)" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#C7559B" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title="Composição por ativo"
          right={chartInfo('Cada fatia representa um ativo. Quanto maior a fatia, maior a alocação percentual desse ticker no consolidado.')}
        >
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

        <Card
          title="Tendência semanal"
          right={chartInfo('Área acima de zero indica ganho simulado na semana. Compare o ritmo entre semanas para ler aceleração ou desaceleração.')}
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={areaData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(37,37,37,0.12)" />
                <XAxis dataKey="week" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="gain" stroke="#E15EF2" fill="#E15EF2" fillOpacity={0.25} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card
        title="Comparação da carteira"
        right={chartInfo('Compara a carteira consolidada com benchmark em risco, liquidez, diversificação, volatilidade e exposição.')}
      >
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" />
              <Radar dataKey="carteira" fill="#3D4D9C" fillOpacity={0.4} stroke="#3D4D9C" />
              <Radar dataKey="benchmark" fill="#C7559B" fillOpacity={0.22} stroke="#C7559B" />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
