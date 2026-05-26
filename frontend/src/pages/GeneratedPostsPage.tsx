import { BarChart3, CalendarClock, Check, ImageIcon, MessageSquare, RefreshCcw, Save, Send, Trash2, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { ApiError, api, errorMessage } from '../lib/api';
import { looksLikeInvalidGeneratedContent } from '../lib/contentQuality';
import { useI18n } from '../lib/i18n';
import type { GeneratedPost, PostAsset, PostMetrics, PostMetricsInput, PublisherRunResult, RecommendationsResponse, ScheduledPost, SocialAccount } from '../types';

const POST_STATUSES = ['draft', 'edited', 'approved', 'rejected', 'scheduled', 'published'];
const SCHEDULABLE_STATUSES = new Set(['approved', 'edited']);
const METRIC_FIELDS = ['impressions', 'reach', 'views', 'likes', 'comments', 'shares', 'saves', 'clicks', 'reactions'] as const;
type MetricField = typeof METRIC_FIELDS[number];
type MetricsDraft = PostMetricsInput;

type ScheduleDraft = {
  platform: string;
  social_account_id: string;
  destination_name: string;
  destination_external_id: string;
  destination_url: string;
  date: string;
  time: string;
  error?: string;
};

function defaultScheduleDraft(post: GeneratedPost): ScheduleDraft {
  const target = new Date(Date.now() + 24 * 60 * 60 * 1000);
  return {
    platform: post.platform || 'LinkedIn',
    social_account_id: '',
    destination_name: '',
    destination_external_id: '',
    destination_url: '',
    date: target.toISOString().slice(0, 10),
    time: `${String(target.getHours()).padStart(2, '0')}:00`,
  };
}

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function defaultMetricsDraft(post: GeneratedPost, metric?: PostMetrics): MetricsDraft {
  return {
    scheduled_post_id: post.active_schedule?.id || metric?.scheduled_post_id || null,
    platform: metric?.platform || post.platform || 'LinkedIn',
    metric_date: metric?.metric_date || todayDate(),
    source: 'manual',
    impressions: metric?.impressions || 0,
    reach: metric?.reach || 0,
    views: metric?.views || 0,
    likes: metric?.likes || 0,
    comments: metric?.comments || 0,
    shares: metric?.shares || 0,
    saves: metric?.saves || 0,
    clicks: metric?.clicks || 0,
    reactions: metric?.reactions || 0,
    raw_metrics: {},
  };
}

function formatLocalDateTime(value?: string) {
  if (!value) return '';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function metricTotal(metric?: PostMetrics) {
  if (!metric) return 0;
  return (metric.likes || 0) + (metric.comments || 0) + (metric.shares || 0) + (metric.saves || 0) + (metric.clicks || 0) + (metric.reactions || 0);
}

function safeGeneratedText(value: string | null | undefined, fallback: string) {
  const text = String(value || '').trim();
  return text && !looksLikeInvalidGeneratedContent(text) ? text : fallback;
}

export default function GeneratedPostsPage() {
  const { t, status } = useI18n();
  const [posts, setPosts] = useState<GeneratedPost[]>([]);
  const [originalPosts, setOriginalPosts] = useState<Record<string, GeneratedPost>>({});
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [assetsByPost, setAssetsByPost] = useState<Record<string, PostAsset[]>>({});
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [schedulesByPost, setSchedulesByPost] = useState<Record<string, ScheduledPost>>({});
  const [scheduleOpen, setScheduleOpen] = useState<Record<string, boolean>>({});
  const [scheduleDrafts, setScheduleDrafts] = useState<Record<string, ScheduleDraft>>({});
  const [metricsByPost, setMetricsByPost] = useState<Record<string, PostMetrics[]>>({});
  const [metricsOpen, setMetricsOpen] = useState<Record<string, boolean>>({});
  const [metricsDrafts, setMetricsDrafts] = useState<Record<string, MetricsDraft>>({});
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);
  const [publisherResult, setPublisherResult] = useState<PublisherRunResult | null>(null);
  const [publisherRunning, setPublisherRunning] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    const [loadedPosts, loadedAccounts, schedules, loadedRecommendations] = await Promise.all([
      api<GeneratedPost[]>('/api/generated-posts'),
      api<SocialAccount[]>('/api/social-accounts'),
      api<ScheduledPost[]>('/api/scheduled-posts'),
      api<RecommendationsResponse>('/api/analytics/recommendations').catch(() => null),
    ]).catch((err) => {
      setError(errorMessage(err, t('common.loadError')));
      return [[], [], [], null] as [GeneratedPost[], SocialAccount[], ScheduledPost[], RecommendationsResponse | null];
    });
    setPosts(loadedPosts);
    setOriginalPosts(Object.fromEntries(loadedPosts.map((post) => [post.id, post])));
    setDirty({});
    setAccounts(loadedAccounts);
    setRecommendations(loadedRecommendations);
    setSchedulesByPost(
      schedules.reduce<Record<string, ScheduledPost>>((acc, schedule) => {
        if (!acc[schedule.generated_post_id]) acc[schedule.generated_post_id] = schedule;
        return acc;
      }, {}),
    );
    const metricsEntries = await Promise.allSettled(
      loadedPosts.map(async (post) => {
        const data = await api<{ metrics: PostMetrics[] }>(`/api/generated-posts/${post.id}/metrics`);
        return [post.id, data.metrics || []] as const;
      }),
    );
    setMetricsByPost(Object.fromEntries(metricsEntries.filter((entry) => entry.status === 'fulfilled').map((entry) => entry.value)));
  }

  useEffect(() => {
    load();
  }, []);

  function updateLocal(postId: string, patch: Partial<GeneratedPost>) {
    setPosts((current) => current.map((post) => (post.id === postId ? { ...post, ...patch } : post)));
    setDirty((current) => ({ ...current, [postId]: true }));
  }

  function replacePost(updated: GeneratedPost) {
    setPosts((current) => current.map((post) => (post.id === updated.id ? updated : post)));
    setOriginalPosts((current) => ({ ...current, [updated.id]: updated }));
    setDirty((current) => ({ ...current, [updated.id]: false }));
  }

  function revertPost(postId: string) {
    const original = originalPosts[postId];
    if (!original) return;
    setPosts((current) => current.map((post) => (post.id === postId ? original : post)));
    setDirty((current) => ({ ...current, [postId]: false }));
  }

  async function update(post: GeneratedPost, nextStatus?: string) {
    setSavingId(post.id);
    setError('');
    try {
      const updated = await api<GeneratedPost>(`/api/generated-posts/${post.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          draft_text: post.draft_text,
          final_text: post.final_text,
          status: nextStatus,
        }),
      });
      replacePost(updated);
    } catch (err) {
      setError(errorMessage(err, t('common.error')));
    } finally {
      setSavingId(null);
    }
  }

  async function regenerate(post: GeneratedPost, mode = 'regenerate_full') {
    setSavingId(post.id);
    setError('');
    try {
      const updated = await api<GeneratedPost>(`/api/generated-posts/${post.id}/regenerate`, { method: 'POST', body: JSON.stringify({ use_llm: true, mode }) });
      replacePost(updated);
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    } finally {
      setSavingId(null);
    }
  }

  async function loadAssets(postId: string) {
    setError('');
    try {
      const data = await api<{ assets: PostAsset[] }>(`/api/generated-posts/${postId}/assets`);
      setAssetsByPost((current) => ({ ...current, [postId]: data.assets || [] }));
    } catch (err) {
      setError(errorMessage(err, t('common.loadError')));
    }
  }

  async function loadMetrics(postId: string) {
    const data = await api<{ metrics: PostMetrics[] }>(`/api/generated-posts/${postId}/metrics`);
    setMetricsByPost((current) => ({ ...current, [postId]: data.metrics || [] }));
    return data.metrics || [];
  }

  function openMetrics(post: GeneratedPost) {
    const latest = metricsByPost[post.id]?.[0];
    setMetricsOpen((current) => ({ ...current, [post.id]: true }));
    setMetricsDrafts((current) => ({ ...current, [post.id]: current[post.id] || defaultMetricsDraft(post, latest) }));
  }

  function updateMetricsDraft(postId: string, patch: Partial<MetricsDraft>) {
    setMetricsDrafts((current) => ({ ...current, [postId]: { ...(current[postId] || ({} as MetricsDraft)), ...patch } }));
  }

  async function saveMetrics(post: GeneratedPost) {
    const draft = metricsDrafts[post.id] || defaultMetricsDraft(post);
    setSavingId(post.id);
    setError('');
    try {
      const payload = { ...draft, source: 'manual', scheduled_post_id: draft.scheduled_post_id || post.active_schedule?.id || null };
      const result = await api<{ metric: PostMetrics }>(`/api/generated-posts/${post.id}/metrics/manual`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      const metrics = await loadMetrics(post.id);
      setMetricsDrafts((current) => ({ ...current, [post.id]: defaultMetricsDraft(post, result.metric || metrics[0]) }));
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    } finally {
      setSavingId(null);
    }
  }

  async function removeMetric(post: GeneratedPost, metric: PostMetrics) {
    setSavingId(post.id);
    setError('');
    try {
      await api(`/api/generated-posts/${post.id}/metrics/${metric.id}`, { method: 'DELETE' });
      const metrics = await loadMetrics(post.id);
      setMetricsDrafts((current) => ({ ...current, [post.id]: defaultMetricsDraft(post, metrics[0]) }));
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    } finally {
      setSavingId(null);
    }
  }

  async function generateVisual(post: GeneratedPost) {
    setSavingId(post.id);
    setError('');
    try {
      const result = await api<{ asset: PostAsset; post: GeneratedPost }>(`/api/generated-posts/${post.id}/assets/generate`, { method: 'POST' });
      replacePost(result.post);
      setAssetsByPost((current) => ({ ...current, [post.id]: [result.asset, ...(current[post.id] || []).filter((asset) => asset.id !== result.asset.id)] }));
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    } finally {
      setSavingId(null);
    }
  }

  async function selectVisual(post: GeneratedPost, asset: PostAsset) {
    setSavingId(post.id);
    setError('');
    try {
      const result = await api<{ asset: PostAsset; post: GeneratedPost }>(`/api/generated-posts/${post.id}/assets/${asset.id}/select`, { method: 'PATCH' });
      replacePost(result.post);
      await loadAssets(post.id);
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    } finally {
      setSavingId(null);
    }
  }

  function openSchedule(post: GeneratedPost) {
    setScheduleOpen((current) => ({ ...current, [post.id]: true }));
    setScheduleDrafts((current) => ({ ...current, [post.id]: current[post.id] || defaultScheduleDraft(post) }));
  }

  function updateScheduleDraft(postId: string, patch: Partial<ScheduleDraft>) {
    setScheduleDrafts((current) => ({ ...current, [postId]: { ...(current[postId] || ({} as ScheduleDraft)), ...patch } }));
  }

  async function schedulePost(post: GeneratedPost) {
    const draft = scheduleDrafts[post.id] || defaultScheduleDraft(post);
    setSavingId(post.id);
    updateScheduleDraft(post.id, { error: undefined });
    try {
      let socialAccountId = draft.social_account_id || null;
      if (!socialAccountId && draft.destination_name.trim()) {
        const account = await api<SocialAccount>('/api/social-accounts/manual', {
          method: 'POST',
          body: JSON.stringify({
            platform: draft.platform,
            display_name: draft.destination_name,
            external_account_id: draft.destination_external_id || null,
            account_url: draft.destination_url || null,
          }),
        });
        socialAccountId = account.id;
        setAccounts((current) => [account, ...current]);
      }
      const scheduledFor = new Date(`${draft.date}T${draft.time || '09:00'}:00`).toISOString();
      const result = await api<{ schedule: ScheduledPost; post: GeneratedPost }>(`/api/generated-posts/${post.id}/schedule`, {
        method: 'POST',
        body: JSON.stringify({
          platform: draft.platform,
          scheduled_for: scheduledFor,
          social_account_id: socialAccountId,
          selected_asset_id: post.selected_asset?.id || null,
        }),
      });
      replacePost(result.post);
      setSchedulesByPost((current) => ({ ...current, [post.id]: result.schedule }));
      setScheduleOpen((current) => ({ ...current, [post.id]: false }));
    } catch (error) {
      const message = error instanceof ApiError ? error.message : t('common.error');
      updateScheduleDraft(post.id, { error: message });
      setError(message);
    } finally {
      setSavingId(null);
    }
  }

  async function cancelSchedule(post: GeneratedPost) {
    if (!post.active_schedule) return;
    setSavingId(post.id);
    try {
      await api<ScheduledPost>(`/api/scheduled-posts/${post.active_schedule.id}/cancel`, { method: 'PATCH' });
      await load();
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    } finally {
      setSavingId(null);
    }
  }

  async function runDueTelegramPublishing() {
    if (!window.confirm(t('publisher.confirmRun'))) return;
    setPublisherRunning(true);
    setError('');
    try {
      const result = await api<PublisherRunResult>('/api/publisher/run-due', { method: 'POST' });
      setPublisherResult(result);
      await load();
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
    } finally {
      setPublisherRunning(false);
    }
  }

  function renderSchedulePanel(post: GeneratedPost) {
    if (!scheduleOpen[post.id]) return null;
    const draft = scheduleDrafts[post.id] || defaultScheduleDraft(post);
    const platformAccounts = accounts.filter((account) => account.platform.toLowerCase() === draft.platform.toLowerCase());
    const canSchedule = SCHEDULABLE_STATUSES.has(post.status);
    const isTelegram = draft.platform.toLowerCase() === 'telegram';
    return (
      <div className="editor-panel">
        <div className="editor-panel__head">
          <div>
            <div className="section-label">{t('schedule.title')}</div>
            <p>{t('schedule.timezoneNote')}</p>
          </div>
          {!canSchedule ? <span className="status-badge status-badge--failed">{t('schedule.requiresApproval')}</span> : null}
        </div>
        <div className="editor-form-grid">
          <label className="form-label">
            {t('schedule.platform')}
            <select className="field" value={draft.platform} onChange={(event) => updateScheduleDraft(post.id, { platform: event.target.value, social_account_id: '' })}>
              {Array.from(new Set([post.platform, 'LinkedIn', 'Telegram', 'Instagram', 'X'].filter(Boolean))).map((platform) => (
                <option key={platform} value={platform}>{platform}</option>
              ))}
            </select>
          </label>
          <label className="form-label">
            {t('schedule.destination')}
            <select className="field" value={draft.social_account_id} onChange={(event) => updateScheduleDraft(post.id, { social_account_id: event.target.value })}>
              <option value="">{t('schedule.noDestination')}</option>
              {platformAccounts.map((account) => <option key={account.id} value={account.id}>{account.display_name}</option>)}
            </select>
          </label>
          {!draft.social_account_id ? (
            <>
              <label className="form-label">
                {t('schedule.destinationName')}
                <input className="field" value={draft.destination_name} onChange={(event) => updateScheduleDraft(post.id, { destination_name: event.target.value })} placeholder={t('schedule.createManualDestination')} />
              </label>
              <label className="form-label">
                {isTelegram ? t('schedule.telegramExternalId') : t('schedule.destinationId')}
                <input className="field" value={draft.destination_external_id} onChange={(event) => updateScheduleDraft(post.id, { destination_external_id: event.target.value })} placeholder={isTelegram ? '@channelusername' : ''} />
              </label>
              <label className="form-label">
                {t('schedule.destinationUrl')}
                <input className="field" value={draft.destination_url} onChange={(event) => updateScheduleDraft(post.id, { destination_url: event.target.value })} placeholder="https://..." />
              </label>
              {isTelegram ? <div className="editor-note">{t('schedule.telegramHelper')}</div> : null}
            </>
          ) : null}
          <label className="form-label">
            {t('schedule.date')}
            <input className="field" type="date" value={draft.date} onChange={(event) => updateScheduleDraft(post.id, { date: event.target.value })} />
          </label>
          <label className="form-label">
            {t('schedule.time')}
            <input className="field" type="time" value={draft.time} onChange={(event) => updateScheduleDraft(post.id, { time: event.target.value })} />
          </label>
        </div>
        <div className="editor-note">
          {t('schedule.selectedVisual')}: {post.selected_asset ? safeGeneratedText(post.selected_asset.alt_text || post.selected_asset.search_query || post.selected_asset.provider, '-') : t('visual.empty')}
        </div>
        {draft.error ? <div className="chat-error">{draft.error}</div> : null}
        <div className="toolbar-actions">
          <button className="primary-button" onClick={() => schedulePost(post)} disabled={!canSchedule || savingId === post.id}>
            <CalendarClock size={16} /> {t('schedule.schedule')}
          </button>
          <button className="secondary-button" onClick={() => setScheduleOpen((current) => ({ ...current, [post.id]: false }))}>{t('common.close')}</button>
        </div>
      </div>
    );
  }

  function renderMetricsPanel(post: GeneratedPost) {
    if (!metricsOpen[post.id]) return null;
    const draft = metricsDrafts[post.id] || defaultMetricsDraft(post, metricsByPost[post.id]?.[0]);
    const latest = metricsByPost[post.id]?.[0];
    const updateNumber = (field: MetricField, value: string) => updateMetricsDraft(post.id, { [field]: Math.max(0, Number(value || 0)) } as Partial<MetricsDraft>);
    return (
      <div className="editor-panel">
        <div className="editor-panel__head">
          <div>
            <div className="section-label">{t('metrics.title')}</div>
            <p>{t('metrics.manualOnly')}</p>
          </div>
          <span className="status-badge status-badge--active">{t('metrics.engagementRate')}: {latest ? `${Number(latest.engagement_rate || 0).toFixed(2)}%` : '-'}</span>
        </div>
        <div className="editor-form-grid metrics-grid">
          <label className="form-label">
            {t('metrics.metricDate')}
            <input className="field" type="date" value={draft.metric_date} onChange={(event) => updateMetricsDraft(post.id, { metric_date: event.target.value })} />
          </label>
          <label className="form-label">
            {t('schedule.platform')}
            <input className="field" value={draft.platform || ''} onChange={(event) => updateMetricsDraft(post.id, { platform: event.target.value })} />
          </label>
          {METRIC_FIELDS.map((field) => (
            <label key={field} className="form-label">
              {t(`metrics.${field}`)}
              <input className="field" min={0} type="number" value={draft[field] || 0} onChange={(event) => updateNumber(field, event.target.value)} />
            </label>
          ))}
        </div>
        <div className="toolbar-actions">
          <button className="primary-button" type="button" onClick={() => saveMetrics(post)} disabled={savingId === post.id}>
            <Save size={16} /> {t('metrics.save')}
          </button>
          <button className="secondary-button" type="button" onClick={() => setMetricsOpen((current) => ({ ...current, [post.id]: false }))}>{t('common.close')}</button>
          {latest ? (
            <button className="secondary-button" type="button" onClick={() => removeMetric(post, latest)} disabled={savingId === post.id}>
              <Trash2 size={16} /> {t('metrics.deleteLatest')}
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  function renderVisual(post: GeneratedPost) {
    const visualText = safeGeneratedText(post.selected_asset?.image_prompt, t('visual.empty'));
    const visualSearch = safeGeneratedText(post.selected_asset?.search_query, '');
    return (
      <div className="post-visual-panel">
        {post.selected_asset?.preview_url ? (
          <img src={post.selected_asset.preview_url} alt={post.selected_asset.alt_text || ''} />
        ) : (
          <div className="post-visual-empty">
            <ImageIcon size={24} />
            <span>{visualText}</span>
          </div>
        )}
        <div className="post-visual-meta">
          <span>{t('visual.provider')}: {post.selected_asset?.provider || '-'}</span>
          {visualSearch ? <span>{t('visual.searchQuery')}: {visualSearch}</span> : null}
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title={t('posts.title')}
        description={t('posts.workspaceDesc')}
        action={
          <div className="toolbar-actions">
            <Link className="secondary-button" to="/chat"><MessageSquare size={16} /> {t('plans.openChat')}</Link>
            <button className="primary-button" type="button" onClick={runDueTelegramPublishing} disabled={publisherRunning}>
              <Send size={16} /> {t('publisher.runDueTelegram')}
            </button>
          </div>
        }
      />
      <ErrorNotice message={error} onRetry={load} />
      {publisherResult ? (
        <div className="panel section-panel">
          <div className="section-title">{t('publisher.result')}</div>
          <p className="muted-text">
            {t('publisher.processed')}: {publisherResult.processed} / {t('publisher.published')}: {publisherResult.published} / {t('publisher.failed')}: {publisherResult.failed} / {t('publisher.skipped')}: {publisherResult.skipped}
          </p>
          <div className="status-pill">{publisherResult.dry_run ? t('publisher.dryRunSimulated') : t('publisher.dryRunOff')}</div>
        </div>
      ) : null}
      <div className="post-workspace-list">
        {posts.length === 0 ? (
          <div className="empty-state empty-state--wide">
            <div>
              <div className="section-title">{t('posts.noPostsTitle')}</div>
              <p className="muted-text">{t('posts.noPostsText')}</p>
              <div className="toolbar-actions mt-4">
                <Link className="primary-button" to="/chat">{t('plans.openChat')}</Link>
                <Link className="secondary-button" to="/content-plans">{t('nav.plans')}</Link>
              </div>
            </div>
          </div>
        ) : null}
        {posts.map((post) => {
          const latestSchedule = post.active_schedule || schedulesByPost[post.id];
          const latestMetric = metricsByPost[post.id]?.[0];
          const lowEngagement = Boolean(latestMetric && recommendations?.low_engagement_posts?.some((item) => String(item.id) === String(post.id)));
          const invalidDraft = looksLikeInvalidGeneratedContent(post.draft_text);
          const invalidFinal = looksLikeInvalidGeneratedContent(post.final_text);
          return (
            <article key={post.id} className="post-work-card panel">
              <div className="post-work-card__head">
                <div>
                  <div className="section-label">{post.platform} / {post.format}</div>
                  <h2>{t('posts.editor')}</h2>
                  <p>{dirty[post.id] ? t('common.unsaved') : t('common.saved')}</p>
                </div>
                <div className="badge-row">
                  <StatusBadge value={post.status} />
                  {latestSchedule ? <StatusBadge value={latestSchedule.status} /> : null}
                </div>
              </div>
              <div className="post-card-layout">
                <aside className="post-side">
                  {renderVisual(post)}
                  {latestSchedule ? (
                    <div className="mini-info-card">
                      <div className="section-label">{t('schedule.active')}</div>
                      <b>{latestSchedule.platform} / {formatLocalDateTime(latestSchedule.scheduled_for)}</b>
                      {latestSchedule.external_post_id?.startsWith('dry-run-') ? <span>{t('publisher.simulated')}: {latestSchedule.external_post_id}</span> : null}
                      {latestSchedule.social_account ? <span>{t('schedule.destination')}: {latestSchedule.social_account.display_name}</span> : null}
                      {latestSchedule.error_message ? <span className="danger-text">{latestSchedule.error_message}</span> : null}
                    </div>
                  ) : null}
                  <div className="mini-info-card">
                    <div className="section-label">{t('metrics.latest')}</div>
                    {latestMetric ? (
                      <>
                        <b>{latestMetric.metric_date} / {latestMetric.platform}</b>
                        <span>{t('metrics.views')}: {latestMetric.views} / {t('metrics.impressions')}: {latestMetric.impressions}</span>
                        <span>{t('metrics.engagementRate')}: {Number(latestMetric.engagement_rate || 0).toFixed(2)}% / {t('metrics.reactions')}: {metricTotal(latestMetric)}</span>
                      </>
                    ) : (
                      <span>{t('metrics.none')}</span>
                    )}
                  </div>
                  {lowEngagement ? <div className="chat-warning">{t('recommendations.lowEngagement')}: {t('recommendations.preliminary')}</div> : null}
                </aside>
                <section className="post-editor-panel">
                  {(invalidDraft || invalidFinal) ? (
                    <div className="chat-warning">
                      {t('posts.invalidGeneratedText')}
                      <div className="toolbar-actions mt-3">
                        <button className="secondary-button text-xs" onClick={() => regenerate(post, 'regenerate_full')} disabled={savingId === post.id}>
                          <RefreshCcw size={14} /> {t('posts.regenerateFull')}
                        </button>
                      </div>
                    </div>
                  ) : null}
                  <label className="form-label">
                    {t('posts.draftText')}
                    <span className="field-help">{t('posts.draftHelp')}</span>
                    <textarea className="field editorial-textarea" value={invalidDraft ? '' : post.draft_text || ''} onChange={(e) => updateLocal(post.id, { draft_text: e.target.value })} placeholder={invalidDraft ? t('posts.replaceInvalidText') : ''} />
                  </label>
                  <label className="form-label">
                    {t('posts.finalText')}
                    <span className="field-help">{t('posts.finalHelp')}</span>
                    <textarea className="field editorial-textarea" value={invalidFinal ? '' : post.final_text || ''} onChange={(e) => updateLocal(post.id, { final_text: e.target.value })} placeholder={invalidFinal ? t('posts.replaceInvalidText') : ''} />
                  </label>
                  <div className="post-status-row">
                    <label className="form-label">
                      {t('posts.status')}
                      <select className="field" value={post.status} onChange={(e) => updateLocal(post.id, { status: e.target.value })}>
                        {POST_STATUSES.map((value) => <option key={value} value={value}>{status(value)}</option>)}
                      </select>
                    </label>
                    <div className="toolbar-actions">
                      <button className="secondary-button text-xs" onClick={() => revertPost(post.id)} disabled={!dirty[post.id] || savingId === post.id}>
                        <RefreshCcw size={14} /> {t('common.revert')}
                      </button>
                      <button className="primary-button text-xs" onClick={() => update(post, post.status)} disabled={savingId === post.id || invalidFinal}>
                        <Save size={14} /> {t('common.save')}
                      </button>
                    </div>
                  </div>
                  <div className="regeneration-toolbar">
                    <button className="secondary-button text-xs" onClick={() => regenerate(post, 'regenerate_full')} disabled={savingId === post.id}><RefreshCcw size={14} /> {t('posts.regenerateFull')}</button>
                    <button className="secondary-button text-xs" onClick={() => regenerate(post, 'improve_current')} disabled={savingId === post.id}>{t('posts.improveFinal')}</button>
                    <button className="secondary-button text-xs" onClick={() => regenerate(post, 'shorter')} disabled={savingId === post.id}>{t('posts.makeShorter')}</button>
                    <button className="secondary-button text-xs" onClick={() => regenerate(post, 'more_expert')} disabled={savingId === post.id}>{t('posts.makeExpert')}</button>
                    <button className="secondary-button text-xs" onClick={() => regenerate(post, 'more_human')} disabled={savingId === post.id}>{t('posts.makeHuman')}</button>
                    <button className="secondary-button text-xs" onClick={() => regenerate(post, 'stronger_hook')} disabled={savingId === post.id}>{t('posts.strongerHook')}</button>
                  </div>
                  <div className="toolbar-actions toolbar-actions--divided">
                    <button className="secondary-button text-xs" onClick={() => generateVisual(post)} disabled={savingId === post.id}>{post.selected_asset ? t('visual.regenerate') : t('visual.generate')}</button>
                    <button className="secondary-button text-xs" onClick={() => loadAssets(post.id)} disabled={savingId === post.id}>{t('visual.select')}</button>
                    <button className="secondary-button text-xs" onClick={() => openMetrics(post)} disabled={savingId === post.id}><BarChart3 size={14} /> {latestMetric ? t('metrics.edit') : t('metrics.add')}</button>
                    <button className="secondary-button text-xs" onClick={() => update(post, 'approved')} disabled={savingId === post.id || invalidFinal}><Check size={14} /> {t('common.approve')}</button>
                    <button className="secondary-button text-xs" onClick={() => update(post, 'rejected')} disabled={savingId === post.id}><X size={14} /> {t('common.reject')}</button>
                    {post.active_schedule ? (
                      <button className="secondary-button text-xs" onClick={() => cancelSchedule(post)} disabled={savingId === post.id}><CalendarClock size={14} /> {t('schedule.cancel')}</button>
                    ) : (
                      <button className="secondary-button text-xs" onClick={() => openSchedule(post)} disabled={savingId === post.id || invalidFinal}><CalendarClock size={14} /> {t('common.scheduleLater')}</button>
                    )}
                  </div>
                  {renderSchedulePanel(post)}
                  {renderMetricsPanel(post)}
                  {assetsByPost[post.id]?.length ? (
                    <div className="asset-grid asset-grid--editorial">
                      {assetsByPost[post.id].map((asset) => (
                        <button key={asset.id} className={`asset-card ${asset.is_selected ? 'is-selected' : ''}`} type="button" onClick={() => selectVisual(post, asset)}>
                          {asset.preview_url ? <img src={asset.preview_url} alt={asset.alt_text || ''} /> : null}
                          <div className="chat-card-title">{asset.provider || t('visual.idea')}</div>
                          <div className="chat-card-meta">{safeGeneratedText(asset.search_query || asset.image_prompt, '-')}</div>
                          <div className="menu-card__cta">{asset.is_selected ? t('visual.selected') : t('visual.select')}</div>
                        </button>
                      ))}
                    </div>
                  ) : null}
                </section>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}
