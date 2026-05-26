import { useI18n } from '../lib/i18n';

type Props = {
  value?: string | null;
};

export function StatusBadge({ value }: Props) {
  const { status } = useI18n();
  const normalized = String(value || 'draft').toLowerCase();
  return <span className={`status-badge status-badge--${normalized}`}>{status(normalized)}</span>;
}
