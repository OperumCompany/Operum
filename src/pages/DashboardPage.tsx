import { ArrowRight, BadgeHelp, BookOpen, ChartColumnIncreasing, CircleAlert, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Button, Card } from '../components/UI';
import { usePortfolios } from '../context/PortfoliosContext';
import { assetsCatalog, newsData, pieSeries } from '../data/mocks';
import { getActivePortfolioSelectionLabel, getPortfolioLabel } from '../utils/portfolios';

const colors = ['#3D4D9C', '#C7559B', '#E15EF2', '#717171', '#A5A5A5'];

function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

function getToneByRisk(risk: number) {
  if (risk <= 2.3) return 'Baixo';
  if (risk <= 3.5) return 'Moderado';
  return 'Mais arrojado';
}

export function DashboardPage() {
  const { activePortfolio, selectedPortfolios, isAllPortfoliosSelected } = usePortfolios();
  const selectedAssets = selectedPortfolios.flatMap((portfolio) => portfolio.assets);
  const totalAllocation = selectedAssets.reduce((sum, asset) => sum + asset.allocation, 0);

  const weightedRisk = selectedAssets.length
    ? selectedAssets.reduce((sum, asset) => {
        const risk = assetsCatalog.find((item) => item.ticker === asset.ticker)?.risk ?? 3;
        return sum + risk * asset.allocation;
      }, 0) / Math.max(totalAllocation, 1)
    : 0;

  const classDistribution = selectedAssets.reduce<Record<string, number>>((acc, asset) => {
    const assetClass = assetsCatalog.find((item) => item.ticker === asset.ticker)?.class ?? 'Outros';
    acc[assetClass] = (acc[assetClass] ?? 0) + asset.allocation;
    return acc;
  }, {});

  const topClassEntry = Object.entries(classDistribution).sort((a, b) => b[1] - a[1])[0];
  const topClassText = topClassEntry ? `${topClassEntry[1].toFixed(0)}% em ${topClassEntry[0]}` : 'Nenhuma classe predominante ainda';

  const compositionData = selectedAssets.length
    ? selectedAssets.map((asset) => ({ name: asset.ticker, value: asset.allocation }))
    : pieSeries;

  const relatedNews = newsData
    .filter((item) => {
      const lowered = normalizeText(`${item.category} ${item.title} ${item.summary}`);
      return ['juros', 'inflação', 'ações', 'renda fixa', 'cripto'].some((term) => lowered.includes(normalizeText(term)));
    })
    .slice(0, 3);

  const nextSteps = [
    {
      title: 'Crie ou importe uma carteira',
      description: 'Comece com uma carteira manual ou use um modelo para explorar a plataforma sem esforço.',
      action: 'Abrir carteiras',
      to: '/carteiras',
    },
    {
      title: 'Adicione seus ativos principais',
      description: 'Inclua os investimentos que mais pesam para receber explicações e comparações mais úteis.',
      action: 'Editar carteira',
      to: activePortfolio && !isAllPortfoliosSelected ? `/carteiras/${activePortfolio.id}` : '/carteiras',
    },
    {
      title: 'Aprofunde quando quiser',
      description: 'Se você já conhece análise de investimentos, acesse o painel técnico com gráficos completos.',
      action: 'Ver painel técnico',
      to: '/dashboard-tecnico',
    },
  ];

  const highlights = [
    {
      label: 'Carteira em foco',
      value: getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected),
      helper: isAllPortfoliosSelected
        ? 'O resumo está usando a visão geral de todas as carteiras.'
        : activePortfolio
          ? 'Essa é a carteira usada no resumo de hoje.'
          : 'Crie uma carteira para começar.',
    },
    {
      label: 'Nível de risco',
      value: weightedRisk ? getToneByRisk(weightedRisk) : 'Indefinido',
      helper: weightedRisk ? `Média estimada de ${weightedRisk.toFixed(1)} em uma escala de 1 a 5.` : 'Adicione ativos para calcular.',
    },
    {
      label: 'Quanto está distribuído',
      value: `${totalAllocation.toFixed(0)}%`,
      helper: totalAllocation >= 100 ? 'Sua alocação já cobre toda a carteira.' : 'Ainda existe espaço sem distribuição definida.',
    },
  ];

  const helperPill = (icon: React.ReactNode, text: string) => (
    <div className="inline-flex items-center gap-2 rounded-full bg-[var(--accent-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--text-main)]">
      {icon}
      <span>{text}</span>
    </div>
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-[var(--border-soft)] bg-[linear-gradient(135deg,rgba(225,94,242,0.08)_0%,rgba(255,255,255,0.92)_48%,rgba(61,77,156,0.12)_100%)] p-6 shadow-[var(--shadow-card)] sm:p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-2xl">
            {helperPill(<Sparkles size={14} />, 'Visão simplificada para entender sua carteira')}
            <h2 className="mt-4 text-3xl font-bold tracking-tight text-[var(--text-main)] sm:text-4xl">
              O que está acontecendo com seus investimentos, sem jargão.
            </h2>
            <p className="mt-4 text-base leading-7 text-[var(--text-muted)]">
              Veja primeiro um resumo claro da carteira ativa. Quando precisar de mais detalhes, o painel técnico continua disponível.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/carteiras">
                <Button>Organizar minha carteira</Button>
              </Link>
              <Link to="/dashboard-tecnico" className="inline-flex items-center gap-2 rounded-2xl border border-[var(--border-soft)] bg-white/75 px-4 py-2.5 text-sm font-semibold text-[var(--text-main)]">
                Abrir painel técnico
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 xl:w-[30rem] xl:grid-cols-1">
            {highlights.map((item) => (
              <div key={item.label} className="rounded-[24px] bg-white/76 p-4 shadow-[0_10px_30px_rgba(37,37,37,0.07)]">
                <p className="text-sm font-semibold text-[var(--text-muted)]">{item.label}</p>
                <p className="mt-2 text-2xl font-bold text-[var(--text-main)]">{item.value}</p>
                <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{item.helper}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.4fr_0.9fr]">
        <Card title="Resumo rápido da sua carteira" right={helperPill(<BadgeHelp size={14} />, 'Entenda em 30 segundos')}>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-[24px] bg-[var(--bg-surface-strong)] p-5">
              <p className="text-sm font-semibold text-[var(--text-muted)]">O que mais chama atenção</p>
              <p className="mt-3 text-2xl font-bold text-[var(--text-main)]">{topClassText}</p>
              <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
                Essa leitura ajuda a perceber onde sua carteira está mais concentrada hoje.
              </p>
            </div>
            <div className="rounded-[24px] bg-[var(--success-soft)] p-5">
              <p className="text-sm font-semibold text-[var(--success-text)]">Leitura simples</p>
              <p className="mt-3 text-xl font-bold text-[var(--text-main)]">
                {weightedRisk <= 2.3
                  ? 'Sua carteira parece mais estável.'
                  : weightedRisk <= 3.5
                    ? 'Sua carteira está equilibrada entre segurança e crescimento.'
                    : 'Sua carteira aceita mais oscilações em busca de retorno.'}
              </p>
              <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
                {selectedAssets.length
                  ? isAllPortfoliosSelected
                    ? 'Essa conclusão usa o consolidado de todas as carteiras selecionadas.'
                    : `Essa conclusão usa a carteira ativa ${activePortfolio ? getPortfolioLabel(activePortfolio) : ''}.`
                  : 'Adicione ativos para liberar uma leitura personalizada.'}
              </p>
            </div>
          </div>

          <div className="mt-4 rounded-[24px] bg-[var(--accent-soft)] p-5">
            <div className="flex items-start gap-3">
              <CircleAlert size={18} className="mt-1 shrink-0 text-[var(--accent)]" />
              <div>
                <p className="font-semibold text-[var(--text-main)]">Próxima melhor ação</p>
                <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">
                  {selectedAssets.length
                    ? 'Revise se a distribuição entre classes faz sentido para o seu objetivo. Se quiser profundidade, use o painel técnico.'
                    : 'Sua experiência fica mais útil quando você adiciona ativos ou importa uma carteira exemplo.'}
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Composição da carteira" right={<Link to="/carteiras" className="text-sm font-semibold text-[var(--brand)]">Editar</Link>}>
          <p className="text-sm leading-6 text-[var(--text-muted)]">
            {isAllPortfoliosSelected
              ? 'Veja como o dinheiro está distribuído no consolidado de todas as carteiras.'
              : 'Veja como o dinheiro da carteira ativa está distribuído entre os ativos mais importantes.'}
          </p>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={compositionData} dataKey="value" nameKey="name" outerRadius={90}>
                  {compositionData.map((_, index) => (
                    <Cell key={index} fill={colors[index % colors.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
        <Card title="Comece por aqui" right={helperPill(<BookOpen size={14} />, 'Passo a passo')}>
          <div className="space-y-3">
            {nextSteps.map((step, index) => (
              <div key={step.title} className="flex items-start gap-4 rounded-[24px] bg-[var(--bg-surface-strong)] p-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-sm font-bold text-[var(--brand)] shadow-sm">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <p className="text-base font-semibold">{step.title}</p>
                  <p className="mt-1 text-sm leading-6 text-[var(--text-muted)]">{step.description}</p>
                </div>
                <Link to={step.to} className="self-center text-sm font-semibold text-[var(--brand)]">
                  {step.action}
                </Link>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Notícias para acompanhar" right={helperPill(<ChartColumnIncreasing size={14} />, 'O que pode impactar sua carteira')}>
          <div className="space-y-3">
            {relatedNews.map((item) => (
              <article key={item.id} className="rounded-[24px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--brand)]">{item.category}</p>
                <h3 className="mt-2 text-base font-semibold text-[var(--text-main)]">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{item.summary}</p>
              </article>
            ))}
            <Link to="/noticias" className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--brand)]">
              Ver mais notícias
              <ArrowRight size={16} />
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
