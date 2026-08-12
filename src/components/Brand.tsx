import { Link } from 'react-router-dom';

export function Brand({ compact = false, to = '/' }: { compact?: boolean; to?: string }) {
  return (
    <Link to={to} className="brand-lockup" aria-label="Operum - página inicial">
      <span className="brand-mark" aria-hidden="true">
        <span />
      </span>
      {!compact && <span className="brand-wordmark">Operum</span>}
    </Link>
  );
}
