import { RefreshCcw } from 'lucide-react';
import { useI18n } from '../lib/i18n';

export function ErrorNotice({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  const { t } = useI18n();
  if (!message) return null;
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border border-coral/30 bg-coral/10 p-3 text-sm font-semibold text-coral" style={{ borderRadius: 8 }}>
      <span>{message}</span>
      {onRetry ? (
        <button className="secondary-button bg-white text-xs" type="button" onClick={onRetry}>
          <RefreshCcw size={14} /> {t('common.retry')}
        </button>
      ) : null}
    </div>
  );
}
