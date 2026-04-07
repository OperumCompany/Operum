import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Button, Card, Input } from '../components/UI';
import { initialChat } from '../data/mocks';
import { ChatMessage } from '../types';
import { readStorage, storageKeys, writeStorage } from '../utils/storage';

const suggestions = ['O que é renda fixa?', 'O que é inflação?', 'O que significa liquidez?', 'Qual a diferença entre CDB e Tesouro?'];

function answer(text: string): string {
  const normalized = text.toLowerCase();
  if (normalized.includes('renda fixa')) return 'Renda fixa são ativos com regras de remuneração conhecidas, como CDB e Tesouro. O risco e a liquidez variam por emissor e prazo.';
  if (normalized.includes('inflação')) return 'Inflação é a alta geral de preços. Quando sobe, reduz o poder de compra e influencia decisões de juros.';
  if (normalized.includes('liquidez')) return 'Liquidez é a facilidade de converter um ativo em dinheiro sem perda relevante de valor.';
  if (normalized.includes('cdb') || normalized.includes('tesouro')) return 'CDB é título bancário com cobertura do FGC em limites. Tesouro é título público, com menor risco de crédito soberano.';
  return 'Posso ajudar com conceitos de mercado, risco, diversificação, inflação, juros e classes de ativos.';
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => readStorage(storageKeys.chat, initialChat));
  const [text, setText] = useState('');

  useEffect(() => {
    writeStorage(storageKeys.chat, messages);
  }, [messages]);

  function send(content: string) {
    if (!content.trim()) return;
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content, createdAt: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) };
    const botMsg: ChatMessage = { id: crypto.randomUUID(), role: 'assistant', content: answer(content), createdAt: userMsg.createdAt };
    setMessages((prev) => [...prev, userMsg, botMsg]);
    setText('');
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(text);
  }

  const lastCount = useMemo(() => messages.length, [messages.length]);

  return (
    <div className="space-y-4">
      <Card title="Chat Operum" right={<span className="text-xs text-[#717171]">{lastCount} mensagens</span>}>
        <div className="max-h-[60vh] space-y-3 overflow-y-auto rounded-xl bg-[#F2F2F2] p-3">
          {messages.map((m) => <div key={m.id} className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${m.role === 'assistant' ? 'bg-white' : 'ml-auto bg-[#3D4D9C] text-white'}`}><p>{m.content}</p><p className="mt-1 text-[11px] opacity-70">{m.createdAt}</p></div>)}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">{suggestions.map((s) => <button key={s} onClick={() => send(s)} className="rounded-full bg-[#E15EF2]/20 px-3 py-1 text-xs hover:bg-[#E15EF2]/30">{s}</button>)}</div>
        <form onSubmit={onSubmit} className="mt-4 flex gap-2"><Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Digite sua dúvida" /><Button type="submit">Enviar</Button></form>
      </Card>
    </div>
  );
}
