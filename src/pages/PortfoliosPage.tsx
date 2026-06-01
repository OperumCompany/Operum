import { FormEvent, useMemo, useState } from 'react';
import { FolderPlus, Sparkles, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Button, Card, Input } from '../components/UI';
import { usePortfolios } from '../context/PortfoliosContext';
import { getActivePortfolioSelectionLabel, getPortfolioLabel } from '../utils/portfolios';

const chartColors = ['#3D4D9C', '#C7559B', '#E15EF2', '#717171', '#A5A5A5'];
const PAGE_SIZE = 10;
const MAX_PAGES = 5;
const MAX_PORTFOLIOS = PAGE_SIZE * MAX_PAGES;

export function PortfoliosPage() {
  const navigate = useNavigate();
  const {
    portfolios,
    activePortfolio,
    activePortfolioId,
    setActivePortfolioId,
    createPortfolio,
    updatePortfolio,
    deletePortfolio,
    deletePortfolios,
    selectedPortfolios,
    isAllPortfoliosSelected,
    loading,
    error,
  } = usePortfolios();
  const [name, setName] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectionMode, setSelectionMode] = useState(false);
  const [page, setPage] = useState(1);

  const composition = useMemo(
    () => activePortfolio?.positions.map((p) => ({ name: p.ticker, value: p.quantity })) ?? [],
    [activePortfolio],
  );

  const totalPages = Math.max(1, Math.min(MAX_PAGES, Math.ceil(portfolios.length / PAGE_SIZE)));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * PAGE_SIZE;
  const pagedPortfolios = portfolios.slice(start, start + PAGE_SIZE);

  async function handleCreatePortfolio(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || portfolios.length >= MAX_PORTFOLIOS) return;
    try {
      await createPortfolio({ name: name.trim() });
      setName('');
      setPage(1);
    } catch {
      // handled by context
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
      // handled by context
    }
  }

  async function handleDeletePortfolio(id: string, portfolioName: string) {
    const confirmed = window.confirm(`Tem certeza que deseja remover a carteira "${portfolioName}"?`);
    if (!confirmed) return;
    try {
      await deletePortfolio(id);
      setSelectedIds((prev) => prev.filter((item) => item !== id));
    } catch {
      // handled by context
    }
  }

  async function handleBulkDelete() {
    if (!selectedIds.length) return;
    const confirmed = window.confirm(`Remover ${selectedIds.length} carteira(s) selecionada(s)?`);
    if (!confirmed) return;
    try {
      await deletePortfolios(selectedIds);
      setSelectedIds([]);
      setSelectionMode(false);
      const nextTotal = Math.max(0, portfolios.length - selectedIds.length);
      const nextPages = Math.max(1, Math.min(MAX_PAGES, Math.ceil(nextTotal / PAGE_SIZE)));
      setPage((prev) => Math.min(prev, nextPages));
    } catch {
      // handled by context
    }
  }

  function togglePortfolioSelection(id: string) {
    setSelectedIds((prev) => (
      prev.includes(id)
        ? prev.filter((item) => item !== id)
        : [...prev, id]
    ));
  }

  function toggleSelectionMode() {
    setSelectionMode((prev) => {
      const next = !prev;
      if (!next) {
        setSelectedIds([]);
      }
      return next;
    });
  }

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
              1. Crie uma carteira. 2. Adicione ativos. 3. Veja analises na plataforma.
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.95fr]">
        <div className="space-y-4">
          <Card title="Criar carteira">
            <form onSubmit={handleCreatePortfolio} className="space-y-3">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Minha reserva e longo prazo" />
              <Button type="submit" className="gap-2" disabled={portfolios.length >= MAX_PORTFOLIOS}>
                <FolderPlus size={16} />
                Salvar carteira
              </Button>
              <p className="text-xs text-[var(--text-muted)]">
                {portfolios.length}/{MAX_PORTFOLIOS} carteiras usadas. Limite de 5 paginas com 10 carteiras cada.
              </p>
            </form>
          </Card>

          <Card
            title="Carteiras salvas"
            right={(
              <div className="flex items-center gap-3">
                <span className="text-sm text-[var(--text-muted)]">{portfolios.length} carteira(s)</span>
                <button
                  type="button"
                  onClick={toggleSelectionMode}
                  className={`inline-flex h-10 w-10 items-center justify-center rounded-2xl border transition ${
                    selectionMode
                      ? 'border-[var(--danger-text)] bg-[var(--danger-text)]/10 text-[var(--danger-text)]'
                      : 'border-[var(--border-soft)] bg-white text-[var(--text-main)] hover:border-[var(--danger-text)]/40'
                  }`}
                  aria-label="Ativar selecao para remover carteiras"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            )}
          >
            {portfolios.length === 0 && (
              <p className="py-4 text-sm text-[var(--text-muted)]">Nenhuma carteira ainda. Crie a primeira acima.</p>
            )}

            {portfolios.length > 0 && selectionMode && (
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-3">
                <p className="text-sm text-[var(--text-main)]">
                  Clique nos blocos das carteiras para selecionar as que deseja excluir.
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-[var(--text-muted)]">{selectedIds.length} selecionada(s)</span>
                  <Button type="button" variant="ghost" disabled={!selectedIds.length} onClick={handleBulkDelete}>
                    <Trash2 size={15} />
                    Remover selecionadas
                  </Button>
                  <Button type="button" variant="ghost" onClick={toggleSelectionMode}>
                    Cancelar
                  </Button>
                </div>
              </div>
            )}

            <div className="space-y-3">
              {pagedPortfolios.map((portfolio) => {
                const isEditing = editingId === portfolio.id;
                const isActive = activePortfolioId === portfolio.id;
                const totalQuantity = portfolio.positions.reduce((sum, position) => sum + position.quantity, 0);
                const isSelected = selectedIds.includes(portfolio.id);

                return (
                  <article
                    key={portfolio.id}
                    className={`rounded-[24px] border bg-[var(--bg-surface-strong)] p-4 ${
                      selectionMode ? 'cursor-pointer transition' : ''
                    } ${
                      isSelected
                        ? 'border-[var(--danger-text)] ring-2 ring-[var(--danger-text)]/20'
                        : 'border-[var(--border-soft)]'
                    }`}
                    onClick={() => {
                      if (selectionMode && !isEditing) {
                        togglePortfolioSelection(portfolio.id);
                      }
                    }}
                  >
                    {isEditing ? (
                      <form onSubmit={saveEdit} className="space-y-3" onClick={(e) => e.stopPropagation()}>
                        <Input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Nome da carteira" />
                        <div className="flex flex-wrap gap-2">
                          <Button type="submit">Salvar</Button>
                          <Button
                            type="button"
                            className="bg-[#717171] shadow-none hover:bg-[#3E3E3E]"
                            onClick={() => setEditingId(null)}
                          >
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
                              {isActive && (
                                <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--accent)]">
                                  Ativa
                                </span>
                              )}
                              {selectionMode && isSelected && (
                                <span className="rounded-full bg-[var(--danger-text)]/10 px-3 py-1 text-xs font-semibold text-[var(--danger-text)]">
                                  Selecionada
                                </span>
                              )}
                            </div>
                          </div>
                          {!isActive && (
                            <button
                              type="button"
                              className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-[var(--text-main)]"
                              onClick={(e) => {
                                e.stopPropagation();
                                setActivePortfolioId(portfolio.id);
                              }}
                            >
                              Usar na analise
                            </button>
                          )}
                        </div>

                        <p className="mt-2 text-xs uppercase tracking-[0.14em] text-[var(--text-muted)]">
                          {portfolio.positions.length} ativo(s) • {totalQuantity.toFixed(0)} unidades
                        </p>

                        <div className="mt-4 flex flex-wrap gap-2">
                          <Button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/carteiras/${portfolio.id}`);
                            }}
                          >
                            Abrir carteira
                          </Button>
                          <button
                            type="button"
                            className="rounded-2xl border border-[var(--border-soft)] px-4 py-2.5 text-sm font-semibold"
                            onClick={(e) => {
                              e.stopPropagation();
                              startEdit(portfolio);
                            }}
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--danger-text)]/25 px-4 py-2.5 text-sm font-semibold text-[var(--danger-text)]"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeletePortfolio(portfolio.id, portfolio.name);
                            }}
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

            {portfolios.length > PAGE_SIZE && (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-[var(--text-muted)]">Pagina {safePage} de {totalPages}</p>
                <div className="flex items-center gap-2">
                  <Button type="button" variant="ghost" disabled={safePage === 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
                    ←
                  </Button>
                  {Array.from({ length: totalPages }, (_, index) => index + 1).map((pageNumber) => (
                    <button
                      key={pageNumber}
                      type="button"
                      onClick={() => setPage(pageNumber)}
                      className={`rounded-2xl px-3 py-2 text-sm font-semibold transition ${
                        pageNumber === safePage
                          ? 'bg-[var(--brand)] text-white'
                          : 'border border-[var(--border-soft)] bg-white text-[var(--text-main)]'
                      }`}
                    >
                      {pageNumber}
                    </button>
                  ))}
                  <Button type="button" variant="ghost" disabled={safePage === totalPages} onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}>
                    →
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Resumo da carteira ativa">
            <p className="text-sm leading-6 text-[var(--text-muted)]">
              {getActivePortfolioSelectionLabel(activePortfolio, isAllPortfoliosSelected)}
            </p>
            <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">
              {isAllPortfoliosSelected
                ? `Entenda rapidamente como as ${selectedPortfolios.length} carteiras estao divididas hoje.`
                : 'Entenda rapidamente como essa carteira esta dividida hoje.'}
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
              {!composition.length && <p className="text-sm text-[var(--text-muted)]">A selecao atual ainda nao possui ativos.</p>}
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
