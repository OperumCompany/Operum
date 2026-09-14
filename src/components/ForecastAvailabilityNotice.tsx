import type { ForecastAvailability } from '../types';

export function ForecastAvailabilityNotice({ availability, portfolio = false }: {
  availability?: ForecastAvailability;
  portfolio?: boolean;
}) {
  if (!availability || availability.status === 'ready') return null;
  const pending = availability.items.some((item) => ['pending', 'running'].includes(item.preparation));
  return (
    <p role="status" className="text-sm text-[var(--text-muted)]">
      {portfolio
        ? 'Cobertura de previsões incompleta. A análise utiliza os dados disponíveis.'
        : 'Modelo treinado indisponível para alguns prazos. Quando houver dados suficientes, a estimativa é provisória e tem baixa confiança.'}
      {' '}{pending
        ? 'Modelos em preparação. Solicite uma nova análise mais tarde para atualizar.'
        : 'A preparação dos modelos não está em andamento. Você pode solicitar uma nova análise mais tarde.'}
    </p>
  );
}
