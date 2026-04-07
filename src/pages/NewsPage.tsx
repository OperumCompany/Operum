import { useMemo, useState } from 'react';
import { Card, Input } from '../components/UI';
import { newsData } from '../data/mocks';
import { NewsCategory } from '../types';

const categories: NewsCategory[] = ['Inflação', 'Juros', 'Tecnologia', 'Criptomoedas', 'Ações', 'Exterior', 'Política econômica', 'Renda fixa'];

export function NewsPage() {
  const [selected, setSelected] = useState<NewsCategory | 'Todas'>('Todas');
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => newsData.filter((n) => (selected === 'Todas' || n.category === selected) && `${n.title} ${n.summary}`.toLowerCase().includes(query.toLowerCase())), [selected, query]);

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Notícias de mercado</h2>
      <Card title="Destaques">
        <div className="grid gap-3 md:grid-cols-2">
          {newsData.filter((n) => n.featured).map((n) => <article key={n.id} className="rounded-xl bg-[#3D4D9C] p-4 text-white"><p className="text-xs opacity-80">{n.category}</p><h3 className="mt-1 font-semibold">{n.title}</h3><p className="mt-2 text-sm opacity-90">{n.summary}</p></article>)}
        </div>
      </Card>
      <Card>
        <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <Input placeholder="Buscar palavra-chave" value={query} onChange={(e) => setQuery(e.target.value)} />
          <div className="flex flex-wrap gap-2">{['Todas', ...categories].map((c) => <button key={c} onClick={() => setSelected(c as NewsCategory | 'Todas')} className={`rounded-full px-3 py-1 text-xs ${selected === c ? 'bg-[#C7559B] text-white' : 'bg-[#A5A5A5]/20'}`}>{c}</button>)}</div>
        </div>
        <div className="space-y-3">
          {filtered.map((n) => (
            <article key={n.id} className="rounded-xl border border-[#A5A5A5]/35 p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs text-[#717171]"><span>{n.date}</span><span>•</span><span>{n.source}</span><span>•</span><span className="font-medium text-[#3D4D9C]">Impacto {n.impact}</span></div>
              <h3 className="mt-2 font-semibold">{n.title}</h3>
              <p className="mt-1 text-sm text-[#3E3E3E]">{n.summary}</p>
            </article>
          ))}
        </div>
      </Card>
    </div>
  );
}
