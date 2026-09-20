import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  ArrowLeft, ArrowRight, BarChart3, BrainCircuit, BriefcaseBusiness, CalendarDays,
  ChevronRight, CircleHelp, Database, Gauge, LineChart, Newspaper, Pause, Play,
  Sparkles, Target, UsersRound,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import './presentation.css';

const logoUrl = new URL('../img/logo.png', import.meta.url).href;

export type SlideDefinition = {
  id: string;
  kicker: string;
  targetSeconds: number;
  note: string;
};

export const pitchSlides: SlideDefinition[] = [
  {
    id: 'dor',
    kicker: '01 · A dor',
    targetSeconds: 45,
    note: 'Todo mundo que investe já passou por isso. Você vê uma notícia importante, o mercado reage, uma pessoa diz que é oportunidade, outra diz que é risco. Você abre gráfico, lê análise, assiste vídeo e termina sabendo mais coisas, mas não necessariamente entendendo melhor o que fazer com elas. O problema do investidor não é falta de informação. É informação demais, velocidade demais e clareza de menos. A pergunta que realmente importa continua sendo: isso muda alguma coisa na minha carteira?',
  },
  {
    id: 'caso-real',
    kicker: '02 · Uma dor real',
    targetSeconds: 35,
    note: 'Essa dificuldade apareceu em pessoas reais. Lucas e Helena representam dois perfis diferentes. Lucas é mais digital, quer velocidade e respostas objetivas. Helena tem mais experiência prática, mas busca segurança, clareza e uma leitura menos confusa sobre onde coloca dinheiro. Os dois conseguem acessar dados, notícias e opiniões. O difícil é transformar isso em uma análise organizada da própria carteira. Foi nesse espaço que enxergamos o Operum.',
  },
  {
    id: 'solucao',
    kicker: '03 · A solução',
    targetSeconds: 35,
    note: 'O Operum é uma plataforma de análise de ativos e carteiras criada para ocupar o espaço entre informação e decisão. Ele conecta dados de mercado, histórico dos ativos, notícias e contexto financeiro em uma única experiência. A partir disso, estrutura possíveis cenários para 1, 2 e 3 meses e transforma essa análise em uma leitura compreensível. O Operum não decide pelo investidor, não promete acertar o mercado e não recomenda compra ou venda. Ele reduz ruído, organiza sinais e melhora a qualidade da análise.',
  },
  {
    id: 'diferencial',
    kicker: '04 · Diferencial tecnológico',
    targetSeconds: 25,
    note: 'Hoje qualquer aplicação consegue conectar uma IA e gerar um texto. Esse não é o nosso diferencial. Nosso diferencial está no pipeline. O Operum combina três camadas: uma inteligência de notícias, que interpreta acontecimentos e impactos; uma inteligência quantitativa, que analisa preço, histórico, volatilidade e comportamento; e uma inteligência de resposta, que transforma sinais técnicos em explicações claras. Por trás disso usamos RAG, busca vetorial, top-k, rerank e dados estruturados. Em outras palavras, nós não perguntamos simplesmente para uma IA o que ela acha de um ativo. Nós entregamos dados e contexto selecionados dentro de um fluxo controlado. Transição para a demo ao vivo, cerca de 3min20: dashboard, carteiras, análise preditiva, notícias e chat.',
  },
  {
    id: 'validacao',
    kicker: '05 · Validação',
    targetSeconds: 35,
    note: 'Depois de construir, precisávamos responder uma pergunta ainda mais importante: isso realmente ajuda alguém? Roberto e Igor tiveram aproximadamente três meses de experiência com o Operum. Durante esse período, acompanharam informações, carteiras e análises pela plataforma. Ambos relataram principalmente duas mudanças: mais organização para analisar ativos e mais contexto antes de tomar decisões. Isso não garante resultado financeiro, mas mostra que pessoas fora da equipe conseguiram estruturar melhor o próprio processo de análise.',
  },
  {
    id: 'mercado',
    kicker: '06 · Mercado',
    targetSeconds: 30,
    note: 'Essa dor aparece dentro de um mercado que continua crescendo. Segundo dados divulgados pela ANBIMA, 60,6 milhões de brasileiros investiam em 2025. A ANBIMA também divulgou R$9,1 trilhões investidos por pessoas físicas no primeiro semestre de 2026. E a B3 chegou a 5,4 milhões de investidores em renda variável em 2025, conforme cobertura citando dados da bolsa. O ponto principal não é só que existem mais investidores. É que existem mais produtos, mais informações e mais decisões para serem tomadas. Quanto mais sofisticado o mercado fica, maior a necessidade de ferramentas que transformem complexidade em entendimento.',
  },
  {
    id: 'modelo',
    kicker: '07 · Modelo de negócio',
    targetSeconds: 40,
    note: 'O Operum foi estruturado para ser um negócio recorrente. O ponto de entrada B2C é uma assinatura de R$29,90 por mês ou R$299 por ano. É um preço pensado para reduzir a barreira de entrada e permitir que o usuário incorpore o Operum à rotina. A estrutura inicial é enxuta: cerca de R$550 de desembolso fixo mensal no MVP, sem remuneração dos fundadores, e custo operacional estimado próximo de R$3 por usuário em uma base de 500 assinantes. Além disso, a inteligência construída para o B2C pode ser licenciada no B2B para fintechs, plataformas e empresas financeiras.',
  },
  {
    id: 'proximos-passos',
    kicker: '08 · Próximos passos',
    targetSeconds: 35,
    note: 'Hoje o Operum está focado em renda variável, porque é onde a combinação de notícias, volatilidade, preço e contexto aparece com mais força. Mas a visão do produto é maior. Queremos expandir para renda fixa, trazendo análises de títulos, taxas, vencimentos, liquidez e cenários de juros. Também queremos criar um diagnóstico de perfil do investidor, identificando se ele tem um perfil mais conservador, moderado ou arrojado. Com isso, o Operum deixa de entregar uma análise igual para todos e passa a adaptar a leitura ao perfil de risco, horizonte e comportamento de cada investidor.',
  },
  {
    id: 'investimento',
    kicker: '09 · Escala + investimento',
    targetSeconds: 50,
    note: 'Até aqui, construímos produto e tecnologia. O próximo desafio é provar distribuição, retenção e escala. Por isso estruturamos uma rodada pre-seed de R$750 mil por 15% da empresa, correspondente a valuation de R$4,25 milhões pre-money e R$5 milhões post-money. O objetivo não é simplesmente financiar operação. É comprar aproximadamente 18 meses para validar as métricas que transformam um bom produto em um negócio escalável: 2 a 3 mil clientes pagantes, R$57 mil a R$85 mil de MRR, margem acima de 80%, CAC até R$60, churn até 4% e primeiros contratos B2B.',
  },
  {
    id: 'fechamento',
    kicker: '10 · Fechamento',
    targetSeconds: 25,
    note: 'O Operum começou há quase dez anos com uma dificuldade pessoal: como transformar tanta informação financeira em algo realmente útil para tomar decisão. Essa pergunta virou uma planilha, a planilha virou uma aplicação, a aplicação se tornou um projeto premiado, e hoje temos um produto funcionando. Agora queremos transformar o Operum em uma empresa. O mercado já tem informação suficiente. O que falta é entendimento. Esse é o Operum.',
  },
];

export const backupSlides: SlideDefinition[] = [
  {
    id: 'backup-rag',
    kicker: 'Backup · RAG',
    targetSeconds: 20,
    note: 'RAG permite que a IA responda usando contexto externo recente e selecionado, em vez de depender apenas da memória do modelo. No Operum, isso reduz alucinação e melhora rastreabilidade.',
  },
  {
    id: 'backup-recuperacao',
    kicker: 'Backup · Recuperação',
    targetSeconds: 20,
    note: 'Chunks, vetorização, top-k e rerank formam a camada de recuperação: quebramos notícias em partes menores, buscamos significado, selecionamos candidatos e reordenamos por relevância antes de gerar a resposta.',
  },
  {
    id: 'backup-defesa',
    kicker: 'Backup · Defesa',
    targetSeconds: 20,
    note: 'Copiar uma chamada de IA é fácil. Copiar o fluxo, a base tratada, o motor de notícias, a análise de carteira, as regras educativas e a experiência integrada é muito mais difícil.',
  },
];

const numberFormatter = new Intl.NumberFormat('pt-BR');

function formatTime(value: number) {
  const minutes = Math.floor(value / 60);
  return `${String(minutes).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
}

function Reveal({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduceMotion ? false : { opacity: 0, y: 18, filter: 'blur(5px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ duration: reduceMotion ? 0 : 0.52, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

function OperumMark({ inverse = false }: { inverse?: boolean }) {
  return <div className={`pitch-brand ${inverse ? 'is-inverse' : ''}`}><img src={logoUrl} alt="Operum" /><span>OPERUM</span></div>;
}

function SectionTitle({ kicker, title, description, light = false }: { kicker: string; title: React.ReactNode; description?: string; light?: boolean }) {
  return <div className={`pitch-heading ${light ? 'is-dark' : ''}`}><Reveal><p className={`pitch-kicker ${light ? 'is-light' : ''}`}>{kicker}</p></Reveal><Reveal delay={0.08}><h1>{title}</h1></Reveal>{description && <Reveal delay={0.16}><p className="pitch-description">{description}</p></Reveal>}</div>;
}

function SlidePain() {
  const signals = ['Notícias', 'Gráficos', 'Selic', 'Dólar', 'Inflação', 'Balanços', 'Opiniões'];
  return <div className="pitch-slide light-slide investor-problem-slide"><div className="pitch-slide-inner investor-problem-layout">
    <SectionTitle kicker="A dor" title={<>Investir ficou mais acessível.<br /><span>Entender o mercado, não.</span></>} description="Informação demais. Velocidade demais. Clareza de menos." />
    <Reveal delay={0.24} className="signal-funnel">
      <div className="signal-cloud">{signals.map((signal, index) => <span key={signal} style={{ '--signal-index': index } as React.CSSProperties}>{signal}</span>)}</div>
      <ChevronRight className="signal-arrow" size={38} />
      <div className="investor-question"><span><CircleHelp size={18} /> pergunta central</span><strong>E o que isso muda<br />na minha carteira?</strong></div>
    </Reveal>
  </div></div>;
}

function SlideRealPain() {
  return <div className="pitch-slide light-slide real-pain-slide"><div className="pitch-slide-inner real-pain-layout">
    <SectionTitle kicker="Uma dor real" title="Dois investidores. O mesmo problema." description="Dados existem. Contexto falta." />
    <div className="persona-grid">
      <Reveal delay={0.22}><article><span>Lucas</span><strong>Digital, rápido, objetivo.</strong><p>Quer entender o mercado sem depender de relatórios enormes ou interpretações espalhadas.</p></article></Reveal>
      <Reveal delay={0.34}><article><span>Helena</span><strong>Experiência prática, busca clareza.</strong><p>Quer segurança, contexto e uma leitura menos confusa sobre onde está colocando dinheiro.</p></article></Reveal>
    </div>
    <Reveal delay={0.48} className="context-gap"><Database size={18} />Dados existem. Contexto falta.</Reveal>
  </div></div>;
}

function SlideSolution() {
  const steps = [
    [Database, 'Dados'],
    [Newspaper, 'Notícias'],
    [Gauge, 'Contexto'],
    [BrainCircuit, 'Análise'],
    [LineChart, 'Cenários'],
    [Target, 'Investidor'],
  ] as const;
  return <div className="pitch-slide close-slide solution-pipeline-slide"><div className="close-glow" /><div className="pitch-slide-inner solution-pipeline-layout">
    <div>
      <Reveal><OperumMark inverse /></Reveal>
      <SectionTitle light kicker="A solução" title="Operum: do ruído ao cenário." description="Uma camada inteligente entre informação e decisão." />
      <Reveal delay={0.34}><p className="solution-principle">O Operum não substitui o investidor. Ele reduz ruído, organiza sinais e melhora a qualidade da análise.</p></Reveal>
    </div>
    <Reveal delay={0.22} className="solution-belt">
      {steps.map(([Icon, label], index) => <article key={label}><Icon size={21} /><span>{label}</span>{index < steps.length - 1 && <ChevronRight size={17} />}</article>)}
      <strong><Sparkles size={17} /> OPERUM</strong>
    </Reveal>
  </div></div>;
}

function SlideTech() {
  const engines = [
    [Newspaper, 'IA de notícias', 'Interpreta acontecimentos e possíveis impactos para ativos, setores e mercado.'],
    [BarChart3, 'IA de investimentos', 'Analisa preço, tendência, volatilidade, histórico, carteira e sinais financeiros.'],
    [BrainCircuit, 'IA de resposta', 'Transforma sinais técnicos em explicações claras, educativas e rastreáveis.'],
  ] as const;
  return <div className="pitch-slide light-slide tech-slide"><div className="pitch-slide-inner tech-layout">
    <SectionTitle kicker="Diferencial tecnológico" title={<>O diferencial não é usar IA.<br /><span>É como usamos IA.</span></>} />
    <div className="engine-grid">{engines.map(([Icon, title, copy], index) => <Reveal key={title} delay={0.2 + index * 0.1}><article><Icon size={24} /><h2>{title}</h2><p>{copy}</p></article></Reveal>)}</div>
    <Reveal delay={0.52} className="core-ai"><Sparkles size={20} /><strong>Operum Core AI</strong><span>RAG · busca vetorial · top-k · rerank · dados estruturados</span></Reveal>
  </div></div>;
}

function SlideValidation() {
  const cards = [
    ['Roberto', '90 dias', 'Mais organização para analisar ativos e mais clareza para acompanhar decisões sobre a carteira.'],
    ['Igor', '90 dias', 'Mais contexto na leitura dos ativos antes de investir e comparar cenários.'],
  ];
  return <div className="pitch-slide light-slide validation-slide"><div className="pitch-slide-inner validation-layout">
    <SectionTitle kicker="Validação" title="A tecnologia precisava funcionar fora da nossa equipe." />
    <Reveal delay={0.22} className="validation-center"><UsersRound size={18} />Experiência real com o produto</Reveal>
    <div className="validation-grid">{cards.map(([name, period, quote], index) => <Reveal key={name} delay={0.3 + index * 0.12}><article className="validation-card"><small>{period}</small><h2>{name}</h2><p>“{quote}”</p></article></Reveal>)}</div>
    <Reveal delay={0.54}><p className="validation-footer">Os relatos representam experiências individuais de teste e não garantia de resultado financeiro.</p></Reveal>
  </div></div>;
}

function SlideMarket() {
  const stats = [
    ['60,6 milhões', 'brasileiros investidores'],
    ['R$ 9,1 trilhões', 'investimentos de pessoas físicas'],
    ['5,4 milhões', 'investidores em renda variável'],
  ];
  return <div className="pitch-slide light-slide market-slide"><div className="pitch-slide-inner market-layout">
    <SectionTitle kicker="Mercado" title="Mais pessoas investem. A decisão fica mais complexa." />
    <div className="market-stats">{stats.map(([value, label], index) => <Reveal key={value} delay={0.22 + index * 0.1}><article><strong>{value}</strong><span>{label}</span></article></Reveal>)}</div>
    <Reveal delay={0.54}><p className="market-source">Fontes: ANBIMA e B3.</p></Reveal>
  </div></div>;
}

function SlideBusiness() {
  const metrics = [
    ['≈ R$550', 'custo fixo mensal MVP*'],
    ['≈ R$3', 'custo por usuário em base de 500'],
    ['>80%', 'margem de contribuição alvo'],
  ];
  return <div className="pitch-slide light-slide business-slide"><div className="pitch-slide-inner business-layout">
    <SectionTitle kicker="Modelo de negócio" title="Uma inteligência. Diferentes formas de monetização." />
    <div className="business-columns">
      <Reveal delay={0.2}><article><BriefcaseBusiness size={28} /><small>B2C</small><strong>R$29,90/mês</strong><span>ou R$299/ano</span><p>Assinatura recorrente para investidores pessoa física acompanharem ativos, carteiras, notícias e simulações.</p></article></Reveal>
      <Reveal delay={0.3}><article><BrainCircuit size={28} /><small>B2B</small><strong>Inteligência como serviço</strong><span>API · licenciamento · integração · white label</span><p>Licenciamento da esteira de análise para fintechs, plataformas financeiras e empresas.</p></article></Reveal>
    </div>
    <Reveal delay={0.42} className="unit-economics">{metrics.map(([value, label]) => <span key={value}><b>{value}</b>{label}</span>)}</Reveal>
  </div></div>;
}

function SlideRoadmap() {
  const steps = [
    ['Hoje', 'Renda variável', 'Análises de ações, ativos acompanhados, notícias, volatilidade, cenários e impacto na carteira.'],
    ['Próximo', 'Renda fixa', 'Leitura de títulos, taxas, vencimentos, liquidez e cenários de juros para ampliar a cobertura.'],
    ['Evolução', 'Perfil do investidor', 'Diagnóstico conservador, moderado ou arrojado para adaptar análises ao risco e horizonte do usuário.'],
  ];
  return <div className="pitch-slide light-slide roadmap-slide"><div className="pitch-slide-inner roadmap-layout">
    <SectionTitle kicker="Próximos passos" title="De análise de ativos para inteligência personalizada." description="Hoje focamos em renda variável. A próxima etapa é ampliar classes de ativos e adaptar a análise ao perfil de cada investidor." />
    <div className="roadmap-grid">{steps.map(([stage, title, copy], index) => <Reveal key={title} delay={0.22 + index * 0.1}><article><small>{stage}</small><h2>{title}</h2><p>{copy}</p></article></Reveal>)}</div>
    <Reveal delay={0.56} className="roadmap-footer"><Sparkles size={18} />A mesma esteira de IA, com análises cada vez mais completas e aderentes ao investidor.</Reveal>
  </div></div>;
}

function SlideInvestment() {
  const allocations = [
    ['Aquisição e marketing', '30%'],
    ['Produto/IA/dev', '25%'],
    ['Equipe/operação', '15%'],
    ['Compliance/jurídico/segurança', '10%'],
    ['Reserva', '8%'],
    ['Infra/dados', '7%'],
    ['Comercial B2B', '5%'],
  ];
  const goals = ['2.000–3.000 clientes', 'R$57k–85k MRR', 'Margem >80%', 'CAC ≤ R$60', 'Churn ≤4%', 'Primeiros contratos B2B'];
  return <div className="pitch-slide close-slide round-slide"><div className="close-glow" /><div className="pitch-slide-inner round-layout">
    <div>
      <SectionTitle light kicker="Escala + investimento" title="Construímos o MVP. Agora queremos provar escala." />
      <Reveal delay={0.22} className="round-ask"><strong>R$750 mil</strong><span>15%</span><p>Pre-money R$4,25M · Post-money R$5M</p></Reveal>
    </div>
    <Reveal delay={0.3} className="round-panel"><h2>Próximos 18 meses</h2><div className="round-goals">{goals.map((goal) => <span key={goal}>{goal}</span>)}</div><div className="allocation-list">{allocations.map(([label, value]) => <div key={label}><span>{label}</span><b>{value}</b><i style={{ width: value }} /></div>)}</div></Reveal>
  </div></div>;
}

function SlideClose() {
  const history = [['2016', 'uma ideia'], ['Excel', 'uma ferramenta pessoal'], ['NEXT 2025', 'um projeto premiado'], ['Hoje', 'um produto']];
  return <div className="pitch-slide close-slide final-slide"><div className="close-glow" /><div className="pitch-slide-inner final-layout">
    <Reveal><OperumMark inverse /></Reveal>
    <Reveal delay={0.18} className="final-history">{history.map(([year, label]) => <span key={year}><b>{year}</b>{label}</span>)}</Reveal>
    <Reveal delay={0.3}><h1>Amanhã,<br />uma empresa.</h1></Reveal>
    <Reveal delay={0.42}><p>O mercado já tem informação suficiente. O que falta é entendimento.</p></Reveal>
    <Reveal delay={0.54} className="final-footer">Informação → contexto → cenários → decisões mais conscientes</Reveal>
  </div></div>;
}

function BackupSlide({ title, subtitle, items }: { title: string; subtitle: string; items: string[] }) {
  return <div className="pitch-slide close-slide backup-slide"><div className="close-glow" /><div className="pitch-slide-inner backup-layout">
    <Reveal><p className="pitch-kicker is-light">Backup técnico</p></Reveal>
    <Reveal delay={0.08}><h1>{title}</h1></Reveal>
    <Reveal delay={0.18}><p>{subtitle}</p></Reveal>
    <div className="backup-list">{items.map((item, index) => <Reveal key={item} delay={0.28 + index * 0.08}><article><span>{String(index + 1).padStart(2, '0')}</span>{item}</article></Reveal>)}</div>
  </div></div>;
}

const pitchComponents = [
  SlidePain,
  SlideRealPain,
  SlideSolution,
  SlideTech,
  SlideValidation,
  SlideMarket,
  SlideBusiness,
  SlideRoadmap,
  SlideInvestment,
  SlideClose,
];

const backupComponents = [
  () => <BackupSlide title="Por que RAG?" subtitle="O mercado muda rápido demais para depender só da memória do modelo." items={['Busca contexto recente antes da resposta.', 'Reduz alucinação ao ancorar a análise em fontes recuperadas.', 'Aumenta rastreabilidade para explicar por que a resposta foi construída.']} />,
  () => <BackupSlide title="Como recuperamos contexto?" subtitle="A resposta nasce de uma seleção controlada de informação relevante." items={['Chunks quebram notícias longas em partes menores.', 'Vetores buscam significado, não apenas palavras iguais.', 'Top-k e rerank filtram e reordenam os melhores candidatos.']} />,
  () => <BackupSlide title="O que dificulta copiar?" subtitle="A vantagem está no sistema completo, não em uma chamada de IA isolada." items={['Motor de notícias, carteira e análise operam juntos.', 'Dados estruturados limitam e orientam a IA.', 'A experiência entrega explicação educativa, não recomendação irresponsável.']} />,
];

export function PresentationPage() {
  const [current, setCurrent] = useState(0);
  const [direction, setDirection] = useState(1);
  const [notesOpen, setNotesOpen] = useState(false);
  const [isRunning, setIsRunning] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const reduceMotion = useReducedMotion();
  const showBackup = useMemo(() => new URLSearchParams(window.location.search).get('backup') === '1', []);
  const activeSlides = showBackup ? [...pitchSlides, ...backupSlides] : pitchSlides;
  const activeComponents = showBackup ? [...pitchComponents, ...backupComponents] : pitchComponents;
  const ActiveSlide = activeComponents[current];
  const totalTarget = useMemo(() => activeSlides.reduce((sum, slide) => sum + slide.targetSeconds, 0), [activeSlides]);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = showBackup ? 'Operum — Pitch + Backup' : 'Operum — Pitch';
    return () => { document.title = previousTitle; };
  }, [showBackup]);

  const goTo = useCallback((next: number) => {
    const normalized = Math.max(0, Math.min(activeSlides.length - 1, next));
    setDirection(normalized >= current ? 1 : -1);
    setCurrent(normalized);
  }, [activeSlides.length, current]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === 'ArrowRight' || event.key === ' ' || event.key === 'PageDown') { event.preventDefault(); goTo(current + 1); }
      if (event.key === 'ArrowLeft' || event.key === 'PageUp') { event.preventDefault(); goTo(current - 1); }
      if (event.key === 'Home') { event.preventDefault(); goTo(0); }
      if (event.key === 'End') { event.preventDefault(); goTo(activeSlides.length - 1); }
      if (event.key.toLowerCase() === 'n') setNotesOpen((open) => !open);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [activeSlides.length, current, goTo]);

  useEffect(() => {
    if (!isRunning) return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [isRunning]);

  const transition = reduceMotion ? { duration: 0 } : { duration: .48, ease: [0.22, 1, 0.36, 1] as const };
  const activeDefinition = activeSlides[current];
  const darkSlides = ['solucao', 'investimento', 'fechamento', 'backup-rag', 'backup-recuperacao', 'backup-defesa'];

  return <main className="presentation-page" aria-label="Pitch Operum">
    <div className="presentation-stage">
      <AnimatePresence initial={false} mode="wait" custom={direction}>
        <motion.div key={activeDefinition.id} className="presentation-slide-host" custom={direction} initial={{ opacity: 0, x: reduceMotion ? 0 : direction * 46 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: reduceMotion ? 0 : direction * -46 }} transition={transition}>
          <ActiveSlide />
        </motion.div>
      </AnimatePresence>
    </div>

    <nav className="presentation-controls" aria-label="Controles da apresentação">
      <button type="button" onClick={() => goTo(current - 1)} disabled={current === 0} aria-label="Slide anterior"><ArrowLeft size={17} /></button>
      <div className="presentation-progress" aria-label={`Slide ${current + 1} de ${activeSlides.length}`}>{activeSlides.map((slide, index) => <button key={slide.id} type="button" className={index === current ? 'is-active' : ''} onClick={() => goTo(index)} aria-label={`Ir para slide ${index + 1}: ${slide.kicker}`}><span /></button>)}</div>
      <button type="button" onClick={() => goTo(current + 1)} disabled={current === activeSlides.length - 1} aria-label="Próximo slide"><ArrowRight size={17} /></button>
      <button type="button" className="notes-trigger" onClick={() => setNotesOpen((open) => !open)} aria-pressed={notesOpen}>Notas <kbd>N</kbd></button>
    </nav>

    <div className={`presentation-meta ${!darkSlides.includes(activeDefinition.id) ? 'is-light' : ''}`}><span>{activeDefinition.kicker}</span><span>{numberFormatter.format(current + 1).padStart(2, '0')} / {numberFormatter.format(activeSlides.length).padStart(2, '0')}</span></div>
    <aside className={`presentation-notes ${notesOpen ? 'is-open' : ''}`} aria-label="Notas do apresentador" aria-hidden={!notesOpen}>
      <div className="notes-top"><div><p>Notas do apresentador</p><strong>{activeDefinition.kicker}</strong></div><button type="button" onClick={() => setNotesOpen(false)} aria-label="Fechar notas">×</button></div>
      <p className="notes-script">{activeDefinition.note}</p>
      <div className="notes-timer"><span><CalendarDays size={16} /> Meta: {formatTime(activeSlides.slice(0, current + 1).reduce((sum, slide) => sum + slide.targetSeconds, 0))}</span><strong>{formatTime(elapsed)} <small>/ {formatTime(totalTarget)}</small></strong><button type="button" onClick={() => setIsRunning((running) => !running)} aria-label={isRunning ? 'Pausar cronômetro' : 'Iniciar cronômetro'}>{isRunning ? <Pause size={15} /> : <Play size={15} />}</button></div>
    </aside>
  </main>;
}
