import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Button, Card, Input } from '../components/UI';
import { initialPortfolios } from '../data/mocks';
import { Portfolio } from '../types';
import { readStorage, storageKeys, writeStorage } from '../utils/storage';

const importModes: Array<{ key: Portfolio['source']; label: string }> = [
  { key: 'csv', label: 'Importar CSV' },
  { key: 'sheet', label: 'Importar planilha' },
  { key: 'example', label: 'Importar carteira exemplo' },
];

export function PortfoliosPage() {
  const navigate = useNavigate();
  const [portfolios, setPortfolios] = useState<Portfolio[]>(() =>
    readStorage<Portfolio[]>(storageKeys.portfolios, initialPortfolios).map((portfolio) => ({
      ...portfolio,
      description: portfolio.description ?? 'Carteira sem descricao.',
    })),
  );
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [activePortfolioId, setActivePortfolioId] = useState<string>('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');

  useEffect(() => {
    if (!activePortfolioId && portfolios.length) {
      setActivePortfolioId(portfolios[0].id);
    }
  }, [activePortfolioId, portfolios]);

  function persist(next: Portfolio[]) {
    setPortfolios(next);
    writeStorage(storageKeys.portfolios, next);
  }

  function createPortfolio(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !description.trim()) return;

    const next: Portfolio = {
      id: crypto.randomUUID(),
      name: name.trim(),
      description: description.trim(),
      assets: [],
      createdAt: new Date().toISOString().slice(0, 10),
      source: 'manual',
    };

    persist([next, ...portfolios]);
    setActivePortfolioId(next.id);
    setName('');
    setDescription('');
  }

  function importPortfolio(source: Portfolio['source']) {
    const base = initialPortfolios[0];
    const next: Portfolio = {
      ...base,
      id: crypto.randomUUID(),
      name: `${base.name} (${source.toUpperCase()})`,
      description: `Carteira importada via ${source.toUpperCase()} para simulacao no Operum.`,
      source,
      createdAt: new Date().toISOString().slice(0, 10),
      assets: base.assets.map((asset) => ({ ...asset, id: crypto.randomUUID() })),
    };

    persist([next, ...portfolios]);
    setActivePortfolioId(next.id);
  }

  function startEdit(portfolio: Portfolio) {
    setEditingId(portfolio.id);
    setEditName(portfolio.name);
    setEditDescription(portfolio.description);
  }

  function saveEdit(e: FormEvent) {
    e.preventDefault();
    if (!editingId || !editName.trim() || !editDescription.trim()) return;

    const next = portfolios.map((portfolio) =>
      portfolio.id === editingId
        ? {
            ...portfolio,
            name: editName.trim(),
            description: editDescription.trim(),
          }
        : portfolio,
    );

    persist(next);
    setEditingId(null);
    setEditName('');
    setEditDescription('');
  }

  const activePortfolio = portfolios.find((portfolio) => portfolio.id === activePortfolioId) ?? portfolios[0];
  const composition = useMemo(
    () => activePortfolio?.assets.map((asset) => ({ name: asset.ticker, value: asset.allocation })) ?? [],
    [activePortfolio],
  );

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card title="Criar carteira">
          <form onSubmit={createPortfolio} className="space-y-3">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome da carteira" />
            <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descricao da carteira" />
            <Button type="submit">Salvar carteira</Button>
          </form>
        </Card>

        <Card title="Importacao mockada">
          <div className="flex flex-wrap gap-2">
            {importModes.map((mode) => (
              <Button key={mode.key} type="button" className="bg-[#717171]" onClick={() => importPortfolio(mode.key)}>
                {mode.label}
              </Button>
            ))}
          </div>
        </Card>

        <Card title="Carteiras salvas">
          <div className="space-y-3">
            {portfolios.map((portfolio) => {
              const isEditing = editingId === portfolio.id;

              return (
                <article key={portfolio.id} className="rounded-xl border border-[#A5A5A5]/35 p-3">
                  {isEditing ? (
                    <form onSubmit={saveEdit} className="space-y-2">
                      <Input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Nome da carteira" />
                      <Input value={editDescription} onChange={(e) => setEditDescription(e.target.value)} placeholder="Descricao" />
                      <div className="flex flex-wrap gap-2">
                        <Button type="submit">Salvar</Button>
                        <Button type="button" className="bg-[#717171]" onClick={() => setEditingId(null)}>
                          Cancelar
                        </Button>
                      </div>
                    </form>
                  ) : (
                    <>
                      <p className="font-semibold">{portfolio.name}</p>
                      <p className="mt-1 text-sm text-[#3E3E3E]">{portfolio.description}</p>
                      <p className="mt-1 text-xs text-[#717171]">
                        {portfolio.assets.length} ativos • {portfolio.createdAt} • origem: {portfolio.source}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button type="button" className="bg-[#3D4D9C]" onClick={() => navigate(`/carteiras/${portfolio.id}`)}>
                          Abrir carteira
                        </Button>
                        <Button type="button" className="bg-[#717171]" onClick={() => startEdit(portfolio)}>
                          Editar
                        </Button>
                        <Button type="button" className="bg-[#A5A5A5]" onClick={() => setActivePortfolioId(portfolio.id)}>
                          Ver composicao
                        </Button>
                      </div>
                    </>
                  )}
                </article>
              );
            })}
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <Card title="Composicao da carteira ativa">
          <p className="mb-2 text-sm text-[#717171]">{activePortfolio?.name ?? 'Sem carteira selecionada'}</p>
          <div className="h-64">
            {!!composition.length && (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={composition} dataKey="value" nameKey="name" outerRadius={80} fill="#3D4D9C" />
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
            {!composition.length && <p className="text-sm text-[#717171]">Essa carteira ainda nao possui ativos.</p>}
          </div>
        </Card>
      </div>
    </div>
  );
}
