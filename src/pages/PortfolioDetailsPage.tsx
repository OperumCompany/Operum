import { FormEvent, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Button, Card, Input } from '../components/UI';
import { assetsCatalog, initialPortfolios, newsData } from '../data/mocks';
import { Portfolio } from '../types';
import { readStorage, storageKeys, writeStorage } from '../utils/storage';

function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

const classToNewsKeywords: Record<string, string[]> = {
  'Renda fixa': ['fixa', 'juros', 'inflacao', 'politica'],
  'AÃ§Ãµes Brasil': ['acoes', 'commodities', 'politica', 'juros'],
  'AÃ§Ãµes EUA': ['exterior', 'tecnologia', 'acoes'],
  Fundos: ['fundos', 'juros', 'exterior'],
  Cripto: ['cripto', 'tecnologia'],
};

export function PortfolioDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [portfolios, setPortfolios] = useState<Portfolio[]>(() =>
    readStorage<Portfolio[]>(storageKeys.portfolios, initialPortfolios).map((portfolio) => ({
      ...portfolio,
      description: portfolio.description ?? 'Carteira sem descricao.',
    })),
  );
  const [assetTicker, setAssetTicker] = useState(assetsCatalog[0].ticker);
  const [allocation, setAllocation] = useState(10);
  const [nameDraft, setNameDraft] = useState('');
  const [descriptionDraft, setDescriptionDraft] = useState('');

  const portfolio = portfolios.find((item) => item.id === id);

  function persist(next: Portfolio[]) {
    setPortfolios(next);
    writeStorage(storageKeys.portfolios, next);
  }

  function updatePortfolio(updater: (current: Portfolio) => Portfolio) {
    if (!portfolio) return;
    const next = portfolios.map((item) => (item.id === portfolio.id ? updater(item) : item));
    persist(next);
  }

  function addAsset(e: FormEvent) {
    e.preventDefault();
    if (!portfolio) return;

    updatePortfolio((current) => ({
      ...current,
      assets: [...current.assets, { id: crypto.randomUUID(), ticker: assetTicker, allocation: Math.max(1, Math.min(100, allocation)) }],
    }));
  }

  function removeAsset(assetId: string) {
    updatePortfolio((current) => ({
      ...current,
      assets: current.assets.filter((asset) => asset.id !== assetId),
    }));
  }

  function savePortfolioDetails(e: FormEvent) {
    e.preventDefault();
    if (!portfolio) return;

    const nextName = nameDraft.trim() || portfolio.name;
    const nextDescription = descriptionDraft.trim() || portfolio.description;

    updatePortfolio((current) => ({
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
        assetClass: catalogAsset?.class ?? 'Classe nao mapeada',
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
      <Card title="Carteira nao encontrada">
        <p className="text-sm text-[#717171]">A carteira solicitada nao existe ou foi removida.</p>
        <Button type="button" className="mt-3" onClick={() => navigate('/carteiras')}>
          Voltar para carteiras
        </Button>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">{portfolio.name}</h2>
          <p className="text-sm text-[#717171]">{portfolio.description}</p>
        </div>
        <Link to="/carteiras" className="rounded-xl bg-[#717171] px-4 py-2 text-sm font-medium text-white">
          Voltar
        </Link>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Card title="Editar carteira">
            <form onSubmit={savePortfolioDetails} className="space-y-3">
              <Input placeholder={portfolio.name} value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} />
              <Input placeholder={portfolio.description} value={descriptionDraft} onChange={(e) => setDescriptionDraft(e.target.value)} />
              <Button type="submit">Salvar alteracoes</Button>
            </form>
          </Card>

          <Card title="Ativos da carteira">
            <form onSubmit={addAsset} className="grid gap-2 sm:grid-cols-3">
              <select
                value={assetTicker}
                onChange={(e) => setAssetTicker(e.target.value)}
                className="rounded-xl border border-[#A5A5A5]/50 px-3 py-2"
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
                placeholder="Alocacao %"
              />
              <Button type="submit">Adicionar ativo simulado</Button>
            </form>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[#717171]">
                    <th className="py-2">Ativo</th>
                    <th>Tipo</th>
                    <th>Risco</th>
                    <th>Alocacao</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {assetsView.map((asset) => (
                    <tr key={asset.id} className="border-t border-[#A5A5A5]/20">
                      <td className="py-2">{asset.ticker} - {asset.name}</td>
                      <td>{asset.assetClass}</td>
                      <td>{asset.risk}/5</td>
                      <td>{asset.allocation}%</td>
                      <td>
                        <button type="button" className="text-[#C7559B]" onClick={() => removeAsset(asset.id)}>
                          Remover
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-[#717171]">Total alocado: {totalAllocation}%</p>
          </Card>

          <Card title="Noticias relacionadas aos tipos de investimento">
            <div className="space-y-4">
              {relatedNews.length === 0 && <p className="text-sm text-[#717171]">Adicione ativos para ver noticias relacionadas.</p>}
              {relatedNews.map((group) => (
                <section key={group.assetClass} className="rounded-xl border border-[#A5A5A5]/30 p-3">
                  <h3 className="text-sm font-semibold">{group.assetClass}</h3>
                  <div className="mt-2 space-y-2">
                    {group.items.map((news) => (
                      <article key={news.id} className="rounded-lg bg-[#F2F2F2] p-3">
                        <p className="text-xs text-[#717171]">{news.date} • {news.source}</p>
                        <p className="mt-1 text-sm font-medium">{news.title}</p>
                        <p className="mt-1 text-sm text-[#3E3E3E]">{news.summary}</p>
                      </article>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Visualizacao de composicao">
            <div className="h-64">
              {!!composition.length && (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={composition} dataKey="value" nameKey="name" outerRadius={80} fill="#3D4D9C" />
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
              {!composition.length && <p className="text-sm text-[#717171]">Sem ativos para visualizar.</p>}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
