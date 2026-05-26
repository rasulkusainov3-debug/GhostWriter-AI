import { CalendarDays, FileText, MessageSquare, Plus } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';

type ContentPlanListItem = {
  id: string;
  title: string;
  status: string;
  week_start?: string;
  updated_at?: string;
  created_at?: string;
  items_count?: number;
  generated_posts_count?: number;
  approved_posts_count?: number;
  scheduled_posts_count?: number;
  published_posts_count?: number;
};

export default function ContentPlansPage() {
  const navigate = useNavigate();
  const { t, status } = useI18n();
  const [plans, setPlans] = useState<ContentPlanListItem[]>([]);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    try {
      setPlans(await api<ContentPlanListItem[]>('/api/content-plans'));
    } catch (err) {
      setError(errorMessage(err, t('common.loadError')));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createPlan() {
    setError('');
    try {
      const data = await api<{ plan: { id: string } }>('/api/content-plans', { method: 'POST', body: JSON.stringify({ title: t('plan.title'), posts_per_week: 5 }) });
      navigate(`/content-plans/${data.plan.id}`);
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    }
  }

  return (
    <>
      <PageHeader
        title={t('plans.title')}
        description={t('plans.workspaceDesc')}
        action={
          <div className="toolbar-actions">
            <Link className="secondary-button" to="/chat"><MessageSquare size={16} /> {t('plans.openChat')}</Link>
            <button className="primary-button" onClick={createPlan}><Plus size={16} /> {t('plans.new')}</button>
          </div>
        }
      />
      <ErrorNotice message={error} onRetry={load} />
      <div className="editorial-grid">
        {plans.length === 0 ? (
          <div className="empty-state empty-state--wide">
            <div>
              <div className="section-title">{t('plans.emptyTitle')}</div>
              <p className="muted-text">{t('plans.emptyText')}</p>
              <div className="toolbar-actions mt-4">
                <button className="primary-button" onClick={createPlan}><Plus size={16} /> {t('plans.new')}</button>
                <Link className="secondary-button" to="/chat">{t('plans.openChat')}</Link>
              </div>
            </div>
          </div>
        ) : null}
        {plans.map((plan) => (
          <Link key={plan.id} to={`/content-plans/${plan.id}`} className="plan-list-card panel">
            <div className="plan-list-card__head">
              <div>
                <h2>{plan.title}</h2>
                <div className="plan-meta"><CalendarDays size={14} /> {t('plans.period')}: {plan.week_start || '-'}</div>
              </div>
              <StatusBadge value={plan.status} />
            </div>
            <div className="plan-stat-row">
              <span><FileText size={14} /> {t('plans.items')}: <b>{plan.items_count || 0}</b></span>
              <span>{t('analytics.generatedPosts')}: <b>{plan.generated_posts_count || 0}</b></span>
              <span>{status('approved')}: <b>{plan.approved_posts_count || 0}</b></span>
              <span>{status('scheduled')}: <b>{plan.scheduled_posts_count || 0}</b></span>
              <span>{status('published')}: <b>{plan.published_posts_count || 0}</b></span>
            </div>
            <div className="plan-list-card__footer">
              <span>{t('plans.updated')}: {String(plan.updated_at || plan.created_at || '').slice(0, 10) || '-'}</span>
              <span className="menu-card__cta">{t('plans.openPlan')}</span>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
