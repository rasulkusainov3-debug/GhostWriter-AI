import { BarChart3, ExternalLink } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';

export default function HistoryPage() {
  const { t, status } = useI18n();
  const [plans, setPlans] = useState<any[]>([]);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    try {
      setPlans(await api<any[]>('/api/content-plans'));
    } catch (err) {
      setError(errorMessage(err, t('common.loadError')));
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <>
      <PageHeader title={t('history.title')} description={t('history.desc')} />
      <ErrorNotice message={error} onRetry={load} />
      <div className="card-list">
        {plans.length === 0 ? <div className="panel section-panel muted-text">{t('common.empty')}</div> : null}
        {plans.map((plan) => (
          <div key={plan.id} className="list-card panel">
            <div>
              <div className="section-title">{plan.title}</div>
              <div className="muted-text">{plan.week_start} / {status(plan.status)}</div>
            </div>
            <div className="flex gap-2">
              <Link className="icon-button" to={`/content-plans/${plan.id}`} title={t('common.open')}><ExternalLink size={18} /></Link>
              <Link className="icon-button" to={`/content-plans/${plan.id}/analytics`} title={t('common.analytics')}><BarChart3 size={18} /></Link>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
