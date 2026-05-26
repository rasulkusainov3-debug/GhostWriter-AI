import { BarChart3, CalendarClock, Check, FileText, MessageSquare, RotateCcw, Save, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { api, errorMessage } from '../lib/api';
import { shortText } from '../lib/contentQuality';
import { useI18n } from '../lib/i18n';
import { ContentPlanItem } from '../types';

type PlanResponse = { plan: any; items: ContentPlanItem[] };

function formatDate(value?: string) {
  if (!value) return '-';
  return String(value).slice(0, 10);
}

export default function ContentPlanPage() {
  const { planId } = useParams();
  const { t, status } = useI18n();
  const [data, setData] = useState<PlanResponse | null>(null);
  const [drafts, setDrafts] = useState<Record<string, ContentPlanItem>>({});
  const [savingItem, setSavingItem] = useState<string | null>(null);
  const [error, setError] = useState('');

  async function load() {
    if (!planId) return;
    setError('');
    try {
      const result = await api<PlanResponse>(`/api/content-plans/${planId}`);
      setData(result);
      setDrafts(Object.fromEntries(result.items.map((item) => [item.id, item])));
    } catch (err) {
      setError(errorMessage(err, t('common.loadError')));
    }
  }

  useEffect(() => {
    load();
  }, [planId]);

  function updateDraft(itemId: string, patch: Partial<ContentPlanItem>) {
    setDrafts((current) => ({ ...current, [itemId]: { ...current[itemId], ...patch } }));
  }

  async function patchItem(item: ContentPlanItem) {
    setSavingItem(item.id);
    setError('');
    try {
      await api(`/api/content-plans/items/${item.id}`, { method: 'PATCH', body: JSON.stringify(item) });
      await load();
    } catch (err) {
      setError(errorMessage(err, t('common.error')));
    } finally {
      setSavingItem(null);
    }
  }

  async function approvePlan() {
    setError('');
    try {
      await api(`/api/content-plans/${planId}/status`, { method: 'PATCH', body: JSON.stringify({ status: 'approved' }) });
      await load();
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    }
  }

  async function generatePosts() {
    setError('');
    try {
      await api(`/api/generated-posts/from-plan/${planId}`, { method: 'POST', body: JSON.stringify({ use_llm: true }) });
      await load();
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    }
  }

  async function generatePostForItem(item: ContentPlanItem) {
    setSavingItem(item.id);
    setError('');
    try {
      await api(`/api/generated-posts/from-plan/${planId}`, { method: 'POST', body: JSON.stringify({ use_llm: true, item_ids: [item.id] }) });
      await load();
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    } finally {
      setSavingItem(null);
    }
  }

  const summary = useMemo(() => {
    const items = data?.items || [];
    const topics = Array.from(new Set(items.map((item) => item.trend_topic || item.post_idea).filter(Boolean) as string[])).slice(0, 5);
    const platforms = Array.from(new Set(items.map((item) => item.platform).filter(Boolean)));
    const formats = Array.from(new Set(items.map((item) => item.format).filter(Boolean)));
    return {
      direction: topics.length ? t('plan.summaryGenerated').replace('{topics}', topics.slice(0, 3).join(', ')) : t('plan.summaryFallback'),
      platforms,
      formats,
      topics,
    };
  }, [data, t]);

  if (!data) return <PageHeader title={t('plan.title')} description={t('common.loading')} />;

  return (
    <>
      <PageHeader
        title={data.plan.title}
        description={`${t('plans.period')}: ${data.plan.week_start || '-'} / ${status(data.plan.status)}`}
        action={
          <div className="toolbar-actions">
            <Link className="secondary-button" to={`/content-plans/${planId}/analytics`}><BarChart3 size={16} /> {t('common.analytics')}</Link>
            <Link className="secondary-button" to="/chat"><MessageSquare size={16} /> {t('plans.openChat')}</Link>
            <button className="secondary-button" onClick={approvePlan}><Check size={16} /> {t('common.approve')}</button>
            <button className="primary-button" onClick={generatePosts}><Sparkles size={16} /> {t('plan.generatePosts')}</button>
            <Link className="secondary-button" to="/generated-posts">{t('plan.posts')}</Link>
          </div>
        }
      />
      <ErrorNotice message={error} onRetry={load} />
      {data.plan.status === 'draft' ? (
        <div className="chat-warning mb-4">
          <b>{t('plan.needsApprovalTitle')}</b>
          <div>{t('plan.needsApprovalText')}</div>
        </div>
      ) : null}
      <div className="plan-detail-layout">
        <aside className="plan-summary panel">
          <div className="section-label">{t('plan.summary')}</div>
          <h2>{t('plan.mainDirection')}</h2>
          <p>{summary.direction}</p>
          <div className="summary-stack">
            <div><span>{t('plans.items')}</span><b>{data.items.length}</b></div>
            <div><span>{t('plan.posts')}</span><b>{data.items.filter((item) => item.generated_post_id).length}</b></div>
            <div><span>{t('profile.platforms')}</span><b>{summary.platforms.join(', ') || '-'}</b></div>
            <div><span>{t('plan.formats')}</span><b>{summary.formats.join(', ') || '-'}</b></div>
          </div>
          {summary.topics.length ? (
            <>
              <div className="section-label mt-4">{t('plan.contentPillars')}</div>
              <div className="tag-list">
                {summary.topics.map((topic) => <span key={topic} className="tag tag-accent">{shortText(topic, 42)}</span>)}
              </div>
            </>
          ) : null}
        </aside>
        <section className="plan-items-section">
          <div className="section-panel panel">
            <div className="work-card__header">
              <div>
                <div className="section-label">{t('plan.items')}</div>
                <div className="section-title">{t('plan.weeklyStructure')}</div>
              </div>
              <StatusBadge value={data.plan.status} />
            </div>
            {data.items.length === 0 ? (
              <div className="empty-state">
                <div>
                  <div className="section-title">{t('plan.noItems')}</div>
                  <p className="muted-text">{t('plan.noItemsText')}</p>
                  <Link className="secondary-button mt-3" to="/chat">{t('plans.openChat')}</Link>
                </div>
              </div>
            ) : null}
            <div className="plan-item-list">
              {data.items.map((item, index) => {
                const draft = drafts[item.id] || item;
                const dirty = JSON.stringify(draft) !== JSON.stringify(item);
                return (
                  <article key={item.id} className="plan-item-card">
                    <div className="plan-item-card__head">
                      <div>
                        <div className="plan-item-index">{t('plan.item')} {index + 1}</div>
                        <h3>{draft.post_idea || item.trend_topic || t('common.empty')}</h3>
                      </div>
                      <div className="badge-row">
                        <StatusBadge value={draft.status} />
                        {item.generated_post_status ? <StatusBadge value={item.generated_post_status} /> : null}
                      </div>
                    </div>
                    <div className="plan-item-meta">
                      <span><FileText size={14} /> {draft.platform || '-'}</span>
                      <span>{draft.format || '-'}</span>
                      <span><CalendarClock size={14} /> {formatDate(draft.scheduled_date)} {String(draft.scheduled_time || '').slice(0, 5)}</span>
                    </div>
                    {item.trend_topic ? (
                      <div className="linked-trend">
                        <span>{t('plan.linkedTrend')}</span>
                        <b>{item.trend_topic}</b>
                        {item.trend_summary ? <p>{shortText(item.trend_summary, 180)}</p> : null}
                      </div>
                    ) : null}
                    <div className="plan-edit-grid">
                      <label className="form-label">
                        {t('schedule.platform')}
                        <input className="field" value={draft.platform} onChange={(e) => updateDraft(item.id, { platform: e.target.value })} />
                      </label>
                      <label className="form-label">
                        {t('plan.format')}
                        <input className="field" value={draft.format} onChange={(e) => updateDraft(item.id, { format: e.target.value })} />
                      </label>
                      <label className="form-label plan-edit-grid__idea">
                        {t('plan.postIdea')}
                        <textarea className="field" value={draft.post_idea || ''} onChange={(e) => updateDraft(item.id, { post_idea: e.target.value })} />
                      </label>
                      <label className="form-label">
                        {t('schedule.date')}
                        <input className="field" type="date" value={String(draft.scheduled_date || '').slice(0, 10)} onChange={(e) => updateDraft(item.id, { scheduled_date: e.target.value } as Partial<ContentPlanItem>)} />
                      </label>
                      <label className="form-label">
                        {t('schedule.time')}
                        <input className="field" type="time" value={String(draft.scheduled_time || '').slice(0, 5)} onChange={(e) => updateDraft(item.id, { scheduled_time: e.target.value } as Partial<ContentPlanItem>)} />
                      </label>
                      <label className="form-label">
                        {t('posts.status')}
                        <select className="field" value={draft.status} onChange={(e) => updateDraft(item.id, { status: e.target.value })}>
                          {['planned', 'generating', 'generated', 'skipped'].map((value) => (
                            <option key={value} value={value}>{status(value)}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="toolbar-actions">
                      <button className="secondary-button text-xs" type="button" onClick={() => patchItem(draft)} disabled={!dirty || savingItem === item.id}>
                        <Save size={14} /> {savingItem === item.id ? t('common.saving') : t('common.save')}
                      </button>
                      <button className="secondary-button text-xs" type="button" onClick={() => updateDraft(item.id, item)} disabled={!dirty || savingItem === item.id}>
                        <RotateCcw size={14} /> {t('common.revert')}
                      </button>
                      <button className="primary-button text-xs" type="button" onClick={() => generatePostForItem(item)} disabled={savingItem === item.id}>
                        <Sparkles size={14} /> {item.generated_post_id ? t('common.regenerate') : t('plan.generatePost')}
                      </button>
                      {item.generated_post_id ? <Link className="secondary-button text-xs" to="/generated-posts">{t('plan.openGeneratedPost')}</Link> : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
