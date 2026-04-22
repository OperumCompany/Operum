import { useMemo, useState } from 'react';
import { Newspaper } from 'lucide-react';
import { Card, Input } from '../components/UI';
import { newsData } from '../data/mocks';
import { NewsCategory } from '../types';

const categories: NewsCategory[] = ['Inflação', 'Juros', 'Tecnologia', 'Criptomoedas', 'Ações', 'Exterior', 'Política econômica', 'Renda fixa'];

export function NewsPage() {
  const [selected, setSelected] = useState<NewsCategory | 'Todas'>('Todas');
  const [query, setQuery] = useState('');

  const filtered = useMemo(
    () =>
      newsData.filter(
        (n) =>
          (selected === 'Todas' || n.category === selected) &&
          `${n.title} ${n.summary}`.toLowerCase().includes(query.toLowerCase()),
      ),
    [selected, query],
  );

  return (
    <div className="space-y-4">
      <section className="rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(61,77,156,0.1)_0%,rgba(255,255,255,0.96)_52%,rgba(199,85,155,0.08)_100%)] p-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-[var(--text-main)]">
              <Newspaper size={16} />
              O que pode mexer com sua carteira
            </div>
            <h2 className="mt-4 text-3xl font-bold">Notícias de mercado com leitura mais clara</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Filtre os temas e acompanhe os assuntos que podem influenciar seus investimentos.
            </p>
          </div>
        </div>
      </section>

      <Card title="Destaques do momento">
        <div className="grid gap-3 md:grid-cols-2">
          {newsData
            .filter((n) => n.featured)
            .map((n) => (
              <article key={n.id} className="rounded-[24px] bg-[#252525] p-5 text-white">
                <p className="text-xs uppercase tracking-[0.14em] opacity-70">{n.category}</p>
                <h3 className="mt-2 text-lg font-semibold">{n.title}</h3>
                <p className="mt-3 text-sm leading-6 text-white/80">{n.summary}</p>
              </article>
            ))}
        </div>
      </Card>

      <Card title="Buscar e filtrar notícias">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <Input placeholder="Buscar palavra-chave" value={query} onChange={(e) => setQuery(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            {['Todas', ...categories].map((c) => (
              <button
                key={c}
                onClick={() => setSelected(c as NewsCategory | 'Todas')}
                className={`rounded-full px-3 py-2 text-xs font-semibold ${
                  selected === c ? 'bg-[var(--brand)] text-white' : 'bg-[var(--bg-surface-strong)] text-[var(--text-main)]'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-3">
          {filtered.map((n) => (
            <article key={n.id} className="rounded-[24px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.12em] text-[var(--text-muted)]">
                <span>{n.date}</span>
                <span>•</span>
                <span>{n.source}</span>
                <span>•</span>
                <span className="font-semibold text-[var(--brand)]">Impacto {n.impact}</span>
              </div>
              <h3 className="mt-2 text-lg font-semibold">{n.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{n.summary}</p>
            </article>
          ))}
        </div>
      </Card>
    </div>
  );
}
