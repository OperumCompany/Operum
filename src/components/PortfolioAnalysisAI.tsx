import { useState } from 'react';
import { Button, Card } from './UI';
import api from '../utils/api';

type OpinionResponse = {
  score: number;
  components: {
    diversification: number;
    correlation_risk: number;
    news_impact: number;
    macro_sensitivity: number;
    forecast_risk: number;
  };
  opinion: string;
  portfolio_id: string;
};

function pct(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}

function scoreLabel(score: number): { label: string; color: string } {
  if (score >= 0.7) return { label: 'Saudável', color: '#22c55e' };
  if (score >= 0.4) return { label: 'Atenção', color: '#eab308' };
  return { label: 'Crítico', color: '#ef4444' };
}

function ComponentBar({ label, value, invert }: { label: string; value: number; invert?: boolean }) {
  const displayValue = invert ? 1 - value : value;
  return (
    <div className="flex items-center gap-3">
      <span className="w-36 text-sm text-[var(--text-muted)]">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--bg-surface-strong)]">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${displayValue * 100}%`, backgroundColor: displayValue >= 0.6 ? '#22c55e' : displayValue >= 0.3 ? '#eab308' : '#ef4444' }}
        />
      </div>
      <span className="w-12 text-right text-sm font-medium">{pct(displayValue)}</span>
    </div>
  );
}

export function PortfolioAnalysisAI({ portfolioId }: { portfolioId: string }) {
  const [data, setData] = useState<OpinionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadOpinion() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<OpinionResponse>(`/models/opinion/${portfolioId}`);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao gerar análise');
    } finally {
      setLoading(false);
    }
  }

  const sl = data ? scoreLabel(data.score) : null;

  return (
    <Card title="Análise da Carteira">
      {!data && !loading && !error && (
        <div className="flex flex-col items-center gap-3 py-4">
          <p className="text-sm text-[var(--text-muted)]">
            Gere uma análise detalhada com base nos ativos, notícias e indicadores de risco.
          </p>
          <Button type="button" onClick={loadOpinion}>
            Gerar análise por IA
          </Button>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-3 py-4">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--brand)] border-t-transparent" />
          <p className="text-sm text-[var(--text-muted)]">Gerando análise...</p>
        </div>
      )}

      {error && (
        <div className="space-y-3 py-2">
          <p className="text-sm text-[var(--danger-text)]">{error}</p>
          <Button type="button" onClick={loadOpinion}>Tentar novamente</Button>
        </div>
      )}

      {data && sl && (
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div
              className="flex h-16 w-16 items-center justify-center rounded-full text-lg font-bold text-white"
              style={{ backgroundColor: sl.color }}
            >
              {pct(data.score)}
            </div>
            <div>
              <p className="text-lg font-bold" style={{ color: sl.color }}>{sl.label}</p>
              <p className="text-xs text-[var(--text-muted)]">Score consolidado da carteira</p>
            </div>
          </div>

          <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4">
            <p className="text-sm leading-relaxed text-[var(--text-main)]">{data.opinion}</p>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Componentes</p>
            <ComponentBar label="Diversificação" value={data.components.diversification} />
            <p className="text-xs leading-relaxed text-[var(--text-muted)]">
              A diversificação mede o quanto a carteira está distribuída entre diferentes ativos. 
              Uma carteira com muitos ativos de setores variados tende a ter maior resiliência 
              a choques específicos. O score é calculado a partir do índice de concentração: 
              quanto menor a concentração em poucos ativos, melhor a diversificação. 
              Esse componente tem peso de 30% no score final por ser um dos pilares 
              da construção de carteiras.
            </p>
            <ComponentBar label="Risco correlação" value={data.components.correlation_risk} invert />
            <p className="text-xs leading-relaxed text-[var(--text-muted)]">
              A correlação entre os ativos indica o quanto eles se movem juntos. 
              Quando a correlação é alta, a diversificação perde eficácia, pois todos os ativos 
              tendem a cair simultaneamente em momentos de estresse. O cálculo usa a matriz de 
              correlação das séries de retorno dos últimos 12 meses. Esse componente tem peso 
              de 20% no score final.
            </p>
            <ComponentBar label="Impacto notícias" value={data.components.news_impact} invert />
            <p className="text-xs leading-relaxed text-[var(--text-muted)]">
              Mede o impacto médio das notícias recentes sobre os ativos da carteira. 
              Quanto mais notícias relevantes e com alto impacto, maior a possibilidade de 
              volatilidade de curto prazo. O cálculo considera o impacto_score de cada notícia 
              que menciona ativos da carteira. Esse componente tem peso de 20% no score final.
            </p>
            <ComponentBar label="Sensibilidade macro" value={data.components.macro_sensitivity} invert />
            <p className="text-xs leading-relaxed text-[var(--text-muted)]">
              A sensibilidade macro avalia a exposição da carteira a fatores econômicos 
              amplos como juros, inflação, câmbio e crescimento do PIB. Ativos de classes 
              como ações (BR_STOCK, US_STOCK) e criptomoedas são mais sensíveis ao cenário 
              macroeconômico, enquanto renda fixa e FIIs podem ter comportamentos distintos. 
              Esse componente tem peso de 15% no score final.
            </p>
            <ComponentBar label="Risco forecast" value={data.components.forecast_risk} invert />
            <p className="text-xs leading-relaxed text-[var(--text-muted)]">
              O risco de forecast é derivado do Value at Risk (VaR) da carteira. 
              Quanto maior o VaR, maior a perda potencial esperada em condições normais 
              de mercado, o que indica um perfil de risco mais elevado para as projeções 
              futuras. Esse componente tem peso de 15% no score final.
            </p>
          </div>

          <Button type="button" variant="ghost" onClick={loadOpinion}>
            Regenerar análise
          </Button>
        </div>
      )}
    </Card>
  );
}
