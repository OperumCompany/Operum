import { FormEvent, useMemo, useState } from 'react';
import { FolderPlus, Sparkles, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Button, Card, Input } from '../components/UI';
import { usePortfolios } from '../context/PortfoliosContext';
import { getActivePortfolioSelectionLabel, getPortfolioLabel } from '../utils/portfolios';

const chartColors = ['#3D4D9C', '#C7559B', '#E15EF2', '#717171', '#A5A5A5'];

export function PortfoliosPage() {
  const navigate = useNavigate();
  const { portfolios, activePortfolio, activePortfolioId, setActivePortfolioId, createPortfolio, updatePortfolio, deletePortfolio, selectedPortfolios, isAllPortfoliosSelected, loading, error } = usePortfolios();
  const [name, setName] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  async function handleCreatePortfolio(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await createPortfolio({ name: name.trim() });
      setName('');
    } catch {
      // error handled by context
    }
  }

  function startEdit(portfolio: { id: string; name: string }) {
    setEditingId(portfolio.id);
    setEditName(portfolio.name);
  }

  async function saveEdit(e: FormEvent) {
    e.preventDefault();
    if (!editingId || !editName.trim()) return;
    try {
      await updatePortfolio(editingId, { name: editName.trim() });
      setEditingId(null);
      setEditName('');
    } catch {
      // error handled by context
    }
  }

  async function handleDeletePortfolio(id: string, name: string) {
    const confirmed = window.confirm(`Tem certeza que deseja remover a carteira "${name}"?`);
    if (!confirmed) return;
    try {
      await deletePortfolio(id);
    } catch {
      // error handled by context
    }
  }

  const composition = useMemo(
    () =>
      activePortfolio?.positions.map((p) => ({ name: p.ticker, value: p.quantity })) ?? [],
    [activePortfolio],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-[var(--text-muted)]">Carregando carteiras...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-[var(--danger-text)]">Erro ao carregar carteiras</p>
        <p className="text-sm text-[var(--text-muted)]">{error}</p>
      </div>
    );
  }

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
              1. Crie uma carteira. 2. Adicione ativos. 3. Veja análises na plataforma.
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.95fr]">
        <div className="space-y-4">
          <Card title="Criar carteira">
            <form onSubmit={handleCreatePortfolio} className="space-y-3">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Minha reserva e longo prazo" />
              <Button type="submit" className="gap-2">
                <FolderPlus size={16} />
                Salvar carteira
              </Button>
            </form>
          </Card>

          <Card title="Carteiras salvas" right={<span className="text-sm text-[var(--text-muted)]">{portfolios.length} carteira(s)</span>}>
            {portfolios.length === 0 && (
              <p className="py-4 text-sm text-[var(--text-muted)]">Nenhuma carteira ainda. Crie a primeira acima.</p>
            )}
            <div className="space-y-3">
              {portfolios.map((portfolio) => {
                const isEditing = editingId === portfolio.id;
                const isActive = activePortfolioId === portfolio.id;
                const totalQuantity = portfolio.positions.reduce((s, p) => s + p.quantity, 0);

                return (
                  <article key={portfolio.id} className="rounded-[24px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
                    {isEditing ? (
                      <form onSubmit={saveEdit} className="space-y-3">
                        <Input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Nome da carteira" />
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
                          {portfolio.positions.length} ativo(s) • {totalQuantity.toFixed(0)} unidades
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
                            onClick={() => handleDeletePortfolio(portfolio.id, portfolio.name)}
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
