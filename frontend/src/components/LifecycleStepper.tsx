import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useI18n } from '../lib/i18n';
import type { LifecycleResponse } from '../types';

type Props = {
  lifecycle?: LifecycleResponse | null;
  compact?: boolean;
};

export function LifecycleStepper({ lifecycle, compact = false }: Props) {
  const { t } = useI18n();
  if (!lifecycle) return null;
  const currentIndex = lifecycle.steps.findIndex((step) => step.status === 'current');
  const visibleSteps = compact
    ? lifecycle.steps.filter((_, index) => Math.abs(index - currentIndex) <= 2 || index === 0 || index === lifecycle.steps.length - 1)
    : lifecycle.steps;
  return (
    <section className="section-panel panel lifecycle-panel">
      <div className="work-card__header">
        <div>
          <div className="section-label">{t('lifecycle.title')}</div>
          <div className="section-title">{t(`lifecycle.state.${lifecycle.current_state}`)}</div>
        </div>
        <span className="status-pill">{t('lifecycle.current')}</span>
      </div>
      <div className="lifecycle-steps">
        {visibleSteps.map((step) => (
          <div key={step.key} className={`lifecycle-step is-${step.status}`}>
            <span className="lifecycle-step__dot" />
            <span>{t(`lifecycle.state.${step.key}`)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function NextActionCard({ lifecycle }: Props) {
  const { t } = useI18n();
  const action = lifecycle?.next_action;
  if (!lifecycle || !action?.type) return null;
  return (
    <section className="section-panel panel next-action-card">
      <div>
        <div className="section-label">{t('lifecycle.nextAction')}</div>
        <div className="section-title">{t(`lifecycle.action.${action.type}`)}</div>
        <p className="muted-text">{t(`lifecycle.state.${lifecycle.current_state}`)}</p>
      </div>
      <Link className="primary-button" to={action.route || '/dashboard'}>
        {t(`lifecycle.action.${action.type}`)} <ArrowRight size={14} />
      </Link>
    </section>
  );
}
