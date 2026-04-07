import { Info } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Card } from '../components/UI';
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
import { areaSeries, assetsCatalog, initialPortfolios, lineSeries, pieSeries, radarSeries } from '../data/mocks';
import { Portfolio } from '../types';
import { readStorage, storageKeys } from '../utils/storage';

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
      <summary className="cursor-pointer list-none rounded-full p-1 text-[#717171] hover:bg-[#A5A5A5]/20">
        <Info size={15} />
      </summary>
      <div className="absolute right-0 z-20 mt-2 w-72 rounded-xl border border-[#A5A5A5]/30 bg-white p-3 text-xs text-[#3E3E3E] shadow-lg">
        {text}
      </div>
    </details>
  );
}

export function DashboardPage() {
  const portfolios = useMemo(
    () =>
      readStorage<Portfolio[]>(storageKeys.portfolios, initialPortfolios).map((portfolio) => ({
        ...portfolio,
        description: portfolio.description ?? 'Carteira sem descricao.',
      })),
    [],
  );
  const [portfolioFilter, setPortfolioFilter] = useState<'all' | string>('all');

  const selectedPortfolios = useMemo(() => {
    if (portfolioFilter === 'all') return portfolios;
    return portfolios.filter((portfolio) => portfolio.id === portfolioFilter);
  }, [portfolioFilter, portfolios]);

  const selectedAssets = selectedPortfolios.flatMap((portfolio) => portfolio.assets);
  const hasAssets = selectedAssets.length > 0;

  const classDistribution = useMemo(() => {
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
              ? 'Acoes EUA'
              : 'Acoes BR';

      totals.set(key, (totals.get(key) ?? 0) + asset.allocation);
    }

    return Array.from(totals.entries()).map(([name, value]) => ({ name, value }));
  }, [selectedAssets]);

  const compositionData = useMemo(() => {
    const totals = new Map<string, number>();

    for (const asset of selectedAssets) {
      totals.set(asset.ticker, (totals.get(asset.ticker) ?? 0) + asset.allocation);
    }

    return Array.from(totals.entries()).map(([name, value]) => ({ name, value }));
  }, [selectedAssets]);

  const weightedRisk = useMemo(() => {
    if (!selectedAssets.length) return 0;

    const total = selectedAssets.reduce((sum, asset) => sum + asset.allocation, 0);
    if (!total) return 0;

    const weighted = selectedAssets.reduce((sum, asset) => {
      const risk = assetsCatalog.find((item) => item.ticker === asset.ticker)?.risk ?? 3;
      return sum + risk * asset.allocation;
    }, 0);

    return weighted / total;
  }, [selectedAssets]);

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
      variation: portfolioFilter === 'all' ? 'Filtro: todas' : 'Filtro: especifica',
    },
    {
      label: 'Ativos monitorados',
      value: String(selectedAssets.length),
      variation: 'Composicao atual',
    },
    {
      label: 'Risco medio (1-5)',
      value: weightedRisk ? weightedRisk.toFixed(2) : '0.00',
      variation: 'Ponderado por alocacao',
    },
    {
      label: 'Alocacao total',
      value: `${selectedAssets.reduce((sum, asset) => sum + asset.allocation, 0).toFixed(0)}%`,
      variation: 'Soma dos ativos',
    },
  ];

  const pieData = compositionData.length ? compositionData : pieSeries;
  const barData = classDistribution.length
    ? classDistribution
    : [
        { name: 'Renda fixa', value: 0 },
        { name: 'Acoes BR', value: 0 },
        { name: 'Acoes EUA', value: 0 },
        { name: 'Fundos', value: 0 },
        { name: 'Cripto', value: 0 },
      ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">Dashboard estrategico</h2>
          <p className="text-sm text-[#717171]">Visao consolidada das carteiras, monitoramento e contexto de mercado.</p>
        </div>
        <div>
          <label className="mb-1 block text-xs text-[#717171]">Filtrar carteiras</label>
          <select
            value={portfolioFilter}
            onChange={(e) => setPortfolioFilter(e.target.value)}
            className="rounded-xl border border-[#A5A5A5]/50 px-3 py-2 text-sm"
          >
            <option value="all">Todas as carteiras</option>
            {portfolios.map((portfolio) => (
              <option key={portfolio.id} value={portfolio.id}>
                {portfolio.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <Card key={metric.label}>
            <p className="text-sm text-[#717171]">{metric.label}</p>
            <p className="mt-1 text-2xl font-bold">{metric.value}</p>
            <p className="mt-2 text-xs text-[#C7559B]">{metric.variation}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card
          title="Evolucao simulada da carteira"
          right={chartInfo('Mostra a tendencia acumulada ao longo dos meses. Linha em alta indica valorizacao no periodo; em queda, perda de valor.')}
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={lineData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#3D4D9C" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title="Distribuicao por categoria"
          right={chartInfo('Barras maiores significam maior exposicao percentual em cada classe de investimento na carteira filtrada.')}
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#C7559B" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title="Composicao por ativo"
          right={chartInfo('Cada fatia representa um ativo. Quanto maior a fatia, maior a alocacao percentual desse ticker.')}
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
          title="Tendencia semanal"
          right={chartInfo('Area acima de zero indica ganho simulado na semana. Compare o ritmo entre semanas para ler aceleracao/desaceleracao.')}
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={areaData}>
                <CartesianGrid strokeDasharray="3 3" />
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
        title="Perfil comparativo"
        right={chartInfo('Compara a carteira com benchmark em risco, liquidez, diversificacao, volatilidade e exposicao. Quanto mais distante do benchmark, maior a diferenca de perfil.')}
      >
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" />
              <Radar dataKey="carteira" fill="#3D4D9C" fillOpacity={0.45} stroke="#3D4D9C" />
              <Radar dataKey="benchmark" fill="#C7559B" fillOpacity={0.25} stroke="#C7559B" />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
