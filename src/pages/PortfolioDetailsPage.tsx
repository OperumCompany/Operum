import { FormEvent, useMemo, useState } from 'react';
import { Info, Newspaper, PlusCircle } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Button, Card, Input } from '../components/UI';
import { usePortfolios } from '../context/PortfoliosContext';
import { assetsCatalog, newsData } from '../data/mocks';
import { getPortfolioLabel } from '../utils/portfolios';

function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

const classToNewsKeywords: Record<string, string[]> = {
  'Renda fixa': ['fixa', 'juros', 'inflação', 'política'],
  'Ações Brasil': ['ações', 'commodities', 'política', 'juros'],
  'Ações EUA': ['exterior', 'tecnologia', 'ações'],
  Fundos: ['fundos', 'juros', 'exterior'],
  Cripto: ['cripto', 'tecnologia'],
};

const chartColors = ['#3D4D9C', '#C7559B', '#E15EF2', '#717171', '#A5A5A5'];

export function PortfolioDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { portfolios, updatePortfolio, setActivePortfolioId, activePortfolioId } = usePortfolios();
  const [assetTicker, setAssetTicker] = useState(assetsCatalog[0].ticker);
  const [allocation, setAllocation] = useState(10);
  const [nameDraft, setNameDraft] = useState('');
  const [descriptionDraft, setDescriptionDraft] = useState('');

  const portfolio = portfolios.find((item) => item.id === id);

  function addAsset(e: FormEvent) {
    e.preventDefault();
    if (!portfolio) return;

    updatePortfolio(portfolio.id, (current) => ({
      ...current,
      assets: [...current.assets, { id: crypto.randomUUID(), ticker: assetTicker, allocation: Math.max(1, Math.min(100, allocation)) }],
    }));
  }

  function removeAsset(assetId: string) {
    if (!portfolio) return;
    updatePortfolio(portfolio.id, (current) => ({
      ...current,
      assets: current.assets.filter((asset) => asset.id !== assetId),
    }));
  }

  function savePortfolioDetails(e: FormEvent) {
    e.preventDefault();
    if (!portfolio) return;

    const nextName = nameDraft.trim() || portfolio.name;
    const nextDescription = descriptionDraft.trim() || portfolio.description;

    updatePortfolio(portfolio.id, (current) => ({
      ...current,
      name: nextName,
      description: nextDescription,
    }));

    setNameDraft('');
    setDescriptionDraft('');
  }

  const assetsView = useMemo(() => {
    if (!portfolio) return [];
    return portfolio.assets.map((asset) => {
      const catalogAsset = assetsCatalog.find((catalogItem) => catalogItem.ticker === asset.ticker);
      return {
        ...asset,
        assetClass: catalogAsset?.class ?? 'Classe não mapeada',
        risk: catalogAsset?.risk ?? 0,
        name: catalogAsset?.name ?? asset.ticker,
      };
    });
  }, [portfolio]);

  const totalAllocation = assetsView.reduce((sum, asset) => sum + asset.allocation, 0);
  const composition = assetsView.map((asset) => ({
    name: asset.ticker,
    value: asset.allocation,
  }));

  const relatedNews = useMemo(() => {
    const classes = new Set(assetsView.map((asset) => asset.assetClass));

    return Array.from(classes)
      .map((assetClass) => {
        const keywords = classToNewsKeywords[assetClass] ?? [];
        const items = newsData
          .filter((news) => {
            const haystack = `${news.category} ${news.title} ${news.summary}`;
            const normalized = normalizeText(haystack);
            return keywords.some((keyword) => normalized.includes(normalizeText(keyword)));
          })
          .slice(0, 3);

        return { assetClass, items };
      })
      .filter((entry) => entry.items.length > 0);
  }, [assetsView]);

  if (!portfolio) {
    return (
      <Card title="Carteira não encontrada">
        <p className="text-sm text-[var(--text-muted)]">A carteira solicitada não existe ou foi removida.</p>
        <Button type="button" className="mt-4" onClick={() => navigate('/carteiras')}>
          Voltar para carteiras
        </Button>
      </Card>
    );
  }

  const isActive = activePortfolioId === portfolio.id;

  return (
    <div className="space-y-4">
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(225,94,242,0.08)_0%,rgba(255,255,255,0.96)_55%,rgba(61,77,156,0.08)_100%)] p-6 shadow-[var(--shadow-card)]">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">Carteira em detalhe</p>
          <h2 className="mt-2 text-3xl font-bold">{getPortfolioLabel(portfolio)}</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">{portfolio.description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!isActive && (
            <Button type="button" onClick={() => setActivePortfolioId(portfolio.id)}>
              Definir como ativa
            </Button>
          )}
          <Link to="/carteiras" className="rounded-2xl border border-[var(--border-soft)] bg-white px-4 py-2.5 text-sm font-semibold text-[var(--text-main)]">
            Voltar
          </Link>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.95fr]">
        <div className="space-y-4">
          <Card title="Editar informações da carteira">
            <form onSubmit={savePortfolioDetails} className="space-y-3">
              <Input placeholder={portfolio.name} value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} />
              <Input placeholder={portfolio.description} value={descriptionDraft} onChange={(e) => setDescriptionDraft(e.target.value)} />
              <Button type="submit">Salvar alterações</Button>
            </form>
          </Card>

          <Card title="Adicionar ativos" right={<span className="text-sm text-[var(--text-muted)]">Próxima ação principal</span>}>
            <div className="mb-4 rounded-[24px] bg-[var(--accent-soft)] p-4 text-sm leading-6 text-[var(--text-muted)]">
              <div className="flex items-start gap-3">
                <Info size={18} className="mt-1 text-[var(--accent)]" />
                <p>Adicione primeiro os ativos mais importantes. Assim o Operum consegue explicar melhor sua carteira.</p>
              </div>
            </div>

            <form onSubmit={addAsset} className="grid gap-2 sm:grid-cols-3">
              <select
                value={assetTicker}
                onChange={(e) => setAssetTicker(e.target.value)}
                className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3"
              >
                {assetsCatalog.map((asset) => (
                  <option key={asset.ticker} value={asset.ticker}>
                    {asset.ticker} - {asset.name}
                  </option>
                ))}
              </select>
              <Input
                type="number"
                min={1}
                max={100}
                value={allocation}
                onChange={(e) => setAllocation(Number(e.target.value))}
                placeholder="Alocação %"
              />
              <Button type="submit" className="gap-2">
                <PlusCircle size={16} />
                Adicionar ativo
              </Button>
            </form>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[var(--text-muted)]">
                    <th className="py-2">Ativo</th>
                    <th>Tipo</th>
                    <th>Risco</th>
                    <th>Alocação</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {assetsView.map((asset) => (
                    <tr key={asset.id} className="border-t border-[var(--border-soft)]">
                      <td className="py-3">{asset.ticker} - {asset.name}</td>
                      <td>{asset.assetClass}</td>
                      <td>{asset.risk}/5</td>
                      <td>{asset.allocation}%</td>
                      <td className="text-right">
                        <button type="button" className="text-sm font-semibold text-[var(--danger-text)]" onClick={() => removeAsset(asset.id)}>
                          Remover
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-[var(--text-muted)]">Total alocado: {totalAllocation}%</p>
          </Card>

          <Card title="Notícias que ajudam a entender essa carteira" right={<Newspaper size={16} className="text-[var(--brand)]" />}>
            <div className="space-y-4">
              {relatedNews.length === 0 && <p className="text-sm text-[var(--text-muted)]">Adicione ativos para ver notícias relacionadas.</p>}
              {relatedNews.map((group) => (
                <section key={group.assetClass} className="rounded-[24px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
                  <h3 className="text-base font-semibold">{group.assetClass}</h3>
                  <div className="mt-3 space-y-2">
                    {group.items.map((news) => (
                      <article key={news.id} className="rounded-[20px] bg-white p-4">
                        <p className="text-xs uppercase tracking-[0.12em] text-[var(--text-muted)]">{news.date} • {news.source}</p>
                        <p className="mt-2 text-sm font-semibold">{news.title}</p>
                        <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{news.summary}</p>
                      </article>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Resumo visual da carteira">
            <p className="text-sm leading-6 text-[var(--text-muted)]">
              Esse gráfico ajuda a enxergar rapidamente quais ativos ocupam mais espaço.
            </p>
            <div className="mt-4 h-64">
              {!!composition.length && (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={composition} dataKey="value" nameKey="name" outerRadius={80}>
                      {composition.map((_, index) => (
                        <Cell key={index} fill={chartColors[index % chartColors.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
              {!composition.length && <p className="text-sm text-[var(--text-muted)]">Sem ativos para visualizar.</p>}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
