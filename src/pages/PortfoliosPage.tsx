import { FormEvent, useMemo, useState } from 'react';
import { ArrowRight, FolderPlus, Sparkles, Trash2, Upload } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Button, Card, Input } from '../components/UI';
import { usePortfolios } from '../context/PortfoliosContext';
import { Portfolio } from '../types';
import { getActivePortfolioSelectionLabel, getPortfolioLabel } from '../utils/portfolios';

const importModes: Array<{ key: Portfolio['source']; label: string; helper: string }> = [
  { key: 'csv', label: 'Importar CSV', helper: 'Envie uma base pronta para acelerar o preenchimento.' },
  { key: 'sheet', label: 'Importar planilha', helper: 'Ideal para quem já organiza a carteira fora da plataforma.' },
  { key: 'example', label: 'Usar exemplo', helper: 'Perfeito para explorar o produto antes de cadastrar dados reais.' },
];

const chartColors = ['#3D4D9C', '#C7559B', '#E15EF2', '#717171', '#A5A5A5'];

export function PortfoliosPage() {
  const navigate = useNavigate();
  const { portfolios, activePortfolio, activePortfolioId, setActivePortfolioId, createPortfolio, importPortfolio, updatePortfolio, deletePortfolio, selectedPortfolios, isAllPortfoliosSelected } = usePortfolios();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');

  function handleCreatePortfolio(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !description.trim()) return;
    createPortfolio({ name, description });
    setName('');
    setDescription('');
  }

  function handleImportPortfolio(source: Portfolio['source']) {
    importPortfolio(source);
  }

  function startEdit(portfolio: Portfolio) {
    setEditingId(portfolio.id);
    setEditName(portfolio.name);
    setEditDescription(portfolio.description);
  }

  function saveEdit(e: FormEvent) {
    e.preventDefault();
    if (!editingId || !editName.trim() || !editDescription.trim()) return;

    updatePortfolio(editingId, (portfolio) => ({
      ...portfolio,
      name: editName.trim(),
      description: editDescription.trim(),
    }));

    setEditingId(null);
    setEditName('');
    setEditDescription('');
  }

  function handleDeletePortfolio(portfolio: Portfolio) {
    const confirmed = window.confirm(`Tem certeza que deseja remover a carteira ${getPortfolioLabel(portfolio)}?`);
    if (!confirmed) return;
    deletePortfolio(portfolio.id);
  }

  const composition = useMemo(
    () => activePortfolio?.assets.map((asset) => ({ name: asset.ticker, value: asset.allocation })) ?? [],
    [activePortfolio],
  );

  return (
    <div className="space-y-5">
      <section className="rounded-[32px] border border-[var(--border-soft)] bg-[linear-gradient(135deg,rgba(225,94,242,0.08)_0%,rgba(255,255,255,0.92)_48%,rgba(61,77,156,0.12)_100%)] p-6 shadow-[var(--shadow-card)] sm:p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm font-semibold text-[var(--text-main)]">
              <Sparkles size={16} />
              Monte sua carteira em poucos passos
            </div>
            <h2 className="mt-4 text-3xl font-bold text-[var(--text-main)] sm:text-4xl">Comece de um jeito simples.</h2>
            <p className="mt-4 text-base leading-7 text-[var(--text-muted)]">
              1. Crie ou importe uma carteira. 2. Adicione ativos. 3. Veja recomendações e análises na plataforma.
            </p>
          </div>
          <div className="rounded-[28px] bg-white/80 p-5 xl:max-w-sm">
            <p className="text-sm font-semibold text-[var(--text-main)]">Não sabe por onde começar?</p>
            <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">
              Use a carteira exemplo para entender o fluxo antes de cadastrar seus próprios dados.
            </p>
            <button
              type="button"
              className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-[var(--brand)]"
              onClick={() => handleImportPortfolio('example')}
            >
              Ver um exemplo pronto
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.95fr]">
        <div className="space-y-4">
          <Card title="1. Criar carteira" right={<span className="text-sm text-[var(--text-muted)]">Ação principal da página</span>}>
            <form onSubmit={handleCreatePortfolio} className="space-y-3">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Minha reserva e longo prazo" />
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descreva o objetivo dessa carteira" />
              <Button type="submit" className="gap-2">
                <FolderPlus size={16} />
                Salvar carteira
              </Button>
            </form>
          </Card>

          <Card title="2. Importar para ganhar tempo">
            <div className="grid gap-3 md:grid-cols-3">
              {importModes.map((mode) => (
                <button
                  key={mode.key}
                  type="button"
                  className="rounded-[24px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4 text-left transition hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(37,37,37,0.08)]"
                  onClick={() => handleImportPortfolio(mode.key)}
                >
                  <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]">
                    <Upload size={16} />
                  </div>
                  <p className="mt-4 font-semibold text-[var(--text-main)]">{mode.label}</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{mode.helper}</p>
                </button>
              ))}
            </div>
          </Card>

          <Card title="3. Carteiras salvas" right={<span className="text-sm text-[var(--text-muted)]">{portfolios.length} carteira(s)</span>}>
            <div className="space-y-3">
              {portfolios.map((portfolio) => {
                const isEditing = editingId === portfolio.id;
                const isActive = activePortfolioId === portfolio.id;

                return (
                  <article key={portfolio.id} className="rounded-[24px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
                    {isEditing ? (
                      <form onSubmit={saveEdit} className="space-y-3">
                        <Input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Nome da carteira" />
                        <Input value={editDescription} onChange={(e) => setEditDescription(e.target.value)} placeholder="Descrição" />
                        <div className="flex flex-wrap gap-2">
                          <Button type="submit">Salvar</Button>
                          <Button type="button" className="bg-[#717171] shadow-none hover:bg-[#3E3E3E]" onClick={() => setEditingId(null)}>
                            Cancelar
                          </Button>
                        </div>
                      </form>
                    ) : (
                      <>
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-lg font-semibold text-[var(--text-main)]">{getPortfolioLabel(portfolio)}</p>
                              {isActive && <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--accent)]">Ativa</span>}
                            </div>
                            <p className="mt-1 text-sm leading-6 text-[var(--text-muted)]">{portfolio.description}</p>
                          </div>
                          {!isActive && (
                            <button
                              type="button"
                              className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-[var(--text-main)]"
                              onClick={() => setActivePortfolioId(portfolio.id)}
                            >
                              Usar na análise
                            </button>
                          )}
                        </div>
                        <p className="mt-2 text-xs uppercase tracking-[0.14em] text-[var(--text-muted)]">
                          {portfolio.assets.length} ativos • {portfolio.createdAt} • origem {portfolio.source}
                        </p>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <Button type="button" onClick={() => navigate(`/carteiras/${portfolio.id}`)}>
                            Abrir carteira
                          </Button>
                          <button type="button" className="rounded-2xl border border-[var(--border-soft)] px-4 py-2.5 text-sm font-semibold" onClick={() => startEdit(portfolio)}>
                            Editar
                          </button>
                          <button
                            type="button"
                            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--danger-text)]/25 px-4 py-2.5 text-sm font-semibold text-[var(--danger-text)]"
                            onClick={() => handleDeletePortfolio(portfolio)}
                          >
                            <Trash2 size={15} />
                            Remover
                          </button>
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
          <Card title="Resumo da carteira ativa">
            <p className="text-sm leading-6 text-[var(--text-muted)]">
              {getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected)}
            </p>
            <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">
              {isAllPortfoliosSelected
                ? `Entenda rapidamente como as ${selectedPortfolios.length} carteiras estão divididas hoje.`
                : 'Entenda rapidamente como essa carteira está dividida hoje.'}
            </p>
            <div className="mt-4 h-64">
              {!!composition.length && (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={composition} dataKey="value" nameKey="name" outerRadius={82}>
                      {composition.map((_, index) => (
                        <Cell key={index} fill={chartColors[index % chartColors.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
              {!composition.length && <p className="text-sm text-[var(--text-muted)]">A seleção atual ainda não possui ativos.</p>}
            </div>
            <Button
              type="button"
              className="mt-3 w-full"
              onClick={() => navigate(activePortfolio && !isAllPortfoliosSelected ? `/carteiras/${activePortfolio.id}` : '/carteiras')}
            >
              {isAllPortfoliosSelected ? 'Abrir lista de carteiras' : 'Adicionar ativos nessa carteira'}
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}
