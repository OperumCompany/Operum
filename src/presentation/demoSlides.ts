export type DemoSlide = {
  id: string;
  kicker: string;
  title: string;
  description: string;
  video: string;
  poster: string;
  targetSeconds: number;
  note: string;
};

export const demoSlides: DemoSlide[] = [
  {
    id: 'demo-visao-geral',
    kicker: '05 · Visão geral',
    title: 'A carteira, em uma leitura que faz sentido.',
    description: 'Valor, evolução, alocação e desempenho reunidos em um único ponto de decisão.',
    video: '/presentation/demos/visao-geral.webm',
    poster: '/presentation/demos/visao-geral.png',
    targetSeconds: 10,
    note: 'Em poucos segundos, o investidor vê a fotografia da carteira: valor atual, capital investido, evolução e distribuição. Não é uma coleção de números; é uma leitura financeira organizada para facilitar o próximo passo.',
  },
  {
    id: 'demo-carteiras',
    kicker: '06 · Carteiras',
    title: 'Organização que acompanha cada estratégia.',
    description: 'Da lista de carteiras à demonstração completa, tudo permanece simples de navegar.',
    video: '/presentation/demos/carteiras.webm',
    poster: '/presentation/demos/carteiras.png',
    targetSeconds: 10,
    note: 'O Operum acompanha diferentes objetivos. Aqui, mostramos a entrada na Carteira Exemplo: uma forma imediata de entender a experiência antes mesmo de cadastrar os próprios ativos.',
  },
  {
    id: 'demo-analise',
    kicker: '07 · Análise em contexto',
    title: 'Do ativo ao cenário, com contexto.',
    description: 'Uma análise demonstra como preço, horizonte e fatores relevantes se conectam.',
    video: '/presentation/demos/analise-ativo.webm',
    poster: '/presentation/demos/analise-ativo.png',
    targetSeconds: 12,
    note: 'Ao abrir um ativo, a plataforma revela uma análise demonstrativa: histórico, perspectiva, confiança e fatores relevantes. O objetivo não é prometer um retorno; é tornar os possíveis cenários mais compreensíveis.',
  },
  {
    id: 'demo-noticias',
    kicker: '08 · Notícias',
    title: 'O mercado ganha relevância quando ganha contexto.',
    description: 'Busca e temas ajudam o investidor a priorizar o que merece atenção.',
    video: '/presentation/demos/noticias.webm',
    poster: '/presentation/demos/noticias.png',
    targetSeconds: 10,
    note: 'Notícias deixam de ser uma sequência infinita de manchetes. Os filtros e a leitura editorial ajudam a aproximar acontecimentos de mercado da carteira e das perguntas do investidor.',
  },
  {
    id: 'demo-chat',
    kicker: '09 · Operum IA',
    title: 'Perguntas reais. Respostas em linguagem clara.',
    description: 'O chat traduz conceitos e o contexto da carteira em uma conversa direta.',
    video: '/presentation/demos/chat.webm',
    poster: '/presentation/demos/chat.png',
    targetSeconds: 10,
    note: 'O chat dá espaço para investigar: tirar dúvidas, aprender conceitos e interpretar informações do próprio Operum. É uma experiência educativa, contextual e acessível.',
  },
];

export function shouldPlayDemo(slideIndex: number, activeIndex: number, reduceMotion: boolean) {
  return slideIndex === activeIndex && !reduceMotion;
}
