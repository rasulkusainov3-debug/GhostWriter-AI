import { CalendarClock, Check, RefreshCcw, Save, Send, Sparkles, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, api, errorMessage } from '../lib/api';
import { looksLikeInvalidGeneratedContent } from '../lib/contentQuality';
import { useI18n } from '../lib/i18n';
import type { PostAsset, ScheduledPost, SocialAccount } from '../types';

type ChatStep = { key?: string; label?: string; status?: string };
type TrendCard = {
  id: number;
  topic: string;
  summary?: string;
  keywords?: string[];
  posts_count?: number;
  source_count?: number;
  relevance_level?: 'high' | 'medium' | 'low';
  relevance_score?: number;
  relevance_reason?: string;
  adaptation_suggestion?: string;
  example_source?: { title?: string; url?: string; source?: string };
  example_sources?: Array<{ title?: string; url?: string; source?: string }>;
};
type GeneratedPostCard = {
  id: string;
  platform: string;
  format: string;
  draft_text?: string;
  final_text: string;
  status: string;
  scheduled_date?: string;
  scheduled_time?: string;
  selected_asset?: PostAsset | null;
  assets_count?: number;
  active_schedule?: ScheduledPost | null;
};
type ChatAction = {
  type?: string;
  status?: string;
  trends?: TrendCard[];
  plan?: { id: string; title?: string; status?: string };
  summary?: {
    direction?: string;
    audience?: string;
    goal?: string;
    platforms?: string[];
    content_pillars?: string[];
    weekly_structure?: Array<{ day?: string; time?: string; platform?: string; format?: string; focus?: string }>;
    trend_based_ideas?: Array<{ trend?: string; idea?: string; platform?: string; format?: string }>;
    suggested_formats?: string[];
    next_steps?: string[];
    target_positioning?: string;
  };
  items?: Array<{ id: string; platform: string; format: string; post_idea?: string; scheduled_date?: string; scheduled_time?: string; status?: string }>;
  posts?: GeneratedPostCard[];
  post?: GeneratedPostCard;
  run_summary?: { queries_used?: string[]; raw_posts_found?: number; trends_found?: number };
  action_required?: 'complete_profile' | 'confirm_profile' | 'find_trends' | 'create_content_plan' | 'approve_content_plan' | 'generate_posts' | 'review_posts' | 'schedule_posts' | 'publish_posts' | 'add_metrics' | 'select_post' | 'select_trend';
};
type Message = { role: string; text: string; action?: ChatAction };
type ChatProfile = {
  name?: string;
  niche?: string;
  profession?: string;
  goal?: string;
  tone?: string;
  audience?: string;
  platforms?: string[];
};
type Provider = { id: string; name: string; configured: boolean; detail: string };
type SaveState = 'idle' | 'unsaved' | 'saving' | 'saved' | 'error';

const POST_STATUSES = ['draft', 'edited', 'approved', 'rejected', 'scheduled'];
const SCHEDULABLE_STATUSES = new Set(['approved', 'edited']);

const INVALID_POST_PHRASES = [
  "i've analyzed",
  'i have analyzed',
  'json data',
  'provided json',
  'overall structure',
  'key findings',
  'article highlights',
  'potential use cases',
  'potential uses',
  'important considerations',
  'this data could',
  'this topic could be used',
  'for a python developer, this is a strong content angle',
  'further considerations',
  'this json represents',
  'the data represents',
  'key fields',
];

const DEBUG_LINE_PATTERNS = [
  /todo:/i,
  /llm_unavailable/i,
  /trends_found/i,
  /^\s*(general_chat|find_new_trends|show_current_trends|agent_help|create_content_plan|generate_posts|refresh_trends|edit_profile)\s*[·:.-]/i,
  /find_new_trends\s*[·:]/i,
  /show_current_trends\s*[·:]/i,
  /agent_help\s*[·:]/i,
  /provider/i,
  /намерение определил/i,
  /intent provider/i,
  /answer provider/i,
  /social_analyzer/i,
  /намерение определил/i,
];

function defaultScheduleFields() {
  const target = new Date(Date.now() + 24 * 60 * 60 * 1000);
  return {
    date: target.toISOString().slice(0, 10),
    time: `${String(target.getHours()).padStart(2, '0')}:00`,
  };
}

function formatLocalDateTime(value?: string) {
  if (!value) return '';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function latestPostFromMessages(messages: Message[]) {
  for (const message of [...messages].reverse()) {
    const action = message.action;
    if (action?.post?.id) return action.post;
    if (action?.posts?.length) return action.posts[0];
  }
  return null;
}

function looksLikeInvalidPost(text?: string) {
  const lower = String(text || '').toLowerCase();
  return looksLikeInvalidGeneratedContent(text) || INVALID_POST_PHRASES.some((phrase) => lower.includes(phrase));
}

function cleanKeyword(value: string) {
  return value.replace(/[[\]{}"]/g, '').replace(/\s+/g, ' ').trim();
}

function cleanAssistantText(text: string) {
  let normalized = String(text || '').replace(/I saved this clarification\.\s*/gi, '');
  const lines = normalized
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !DEBUG_LINE_PATTERNS.some((pattern) => pattern.test(line)));
  normalized = lines.join('\n');
  if (looksLikeInvalidPost(normalized)) return '';
  return normalized.trim();
}

function ExpandableText({
  text,
  showLabel,
  hideLabel,
  className = '',
  defaultExpanded = false,
}: {
  text?: string;
  showLabel: string;
  hideLabel: string;
  className?: string;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const value = String(text || '').trim();
  if (!value) return null;
  const isLong = value.length > 280 || value.split(/\r?\n/).length > 5;
  return (
    <div className={`expandable-text-wrap ${className}`}>
      <div className={`expandable-text ${!expanded && isLong ? 'is-collapsed' : ''}`}>
        {value}
        {!expanded && isLong ? <span className="expandable-text__fade" /> : null}
      </div>
      {isLong ? (
        <button className="expandable-text__toggle" type="button" onClick={() => setExpanded((current) => !current)}>
          {expanded ? hideLabel : showLabel}
        </button>
      ) : null}
    </div>
  );
}

export default function ChatPage() {
  const { t, status } = useI18n();
  const [messages, setMessages] = useState<Message[]>([]);
  const [profile, setProfile] = useState<ChatProfile | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [progressSteps, setProgressSteps] = useState<ChatStep[]>([]);
  const [progressTick, setProgressTick] = useState(0);
  const [processingKey, setProcessingKey] = useState('answer');
  const [longWaitLevel, setLongWaitLevel] = useState(0);
  const [selectedPost, setSelectedPost] = useState<GeneratedPostCard | null>(null);
  const [postDraft, setPostDraft] = useState({ draft_text: '', final_text: '', status: 'draft' });
  const [previewEditing, setPreviewEditing] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [showLowTrends, setShowLowTrends] = useState(false);
  const [visualAssets, setVisualAssets] = useState<PostAsset[]>([]);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [scheduleFields, setScheduleFields] = useState(defaultScheduleFields);
  const [scheduleDestinationName, setScheduleDestinationName] = useState('');
  const [scheduleDestinationExternalId, setScheduleDestinationExternalId] = useState('');
  const [scheduleDestinationUrl, setScheduleDestinationUrl] = useState('');
  const [scheduleAccountId, setScheduleAccountId] = useState('');
  const [scheduleError, setScheduleError] = useState('');
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    api<{ messages: Message[]; profile: ChatProfile | null }>('/api/chat')
      .then((data) => {
        const loadedMessages = data.messages || [];
        setMessages(loadedMessages);
        setProfile(data.profile || null);
        const latestPost = latestPostFromMessages(loadedMessages);
        if (latestPost) selectPost(latestPost, false);
      })
      .catch((err) => {
        setMessages([]);
        setActionError(errorMessage(err, t('common.loadError')));
      });
    api<{ providers: Provider[] }>('/api/integrations/model-status')
      .then((data) => setProviders(data.providers || []))
      .catch(() => setProviders([]));
    api<SocialAccount[]>('/api/social-accounts')
      .then((data) => setAccounts(data || []))
      .catch(() => setAccounts([]));
  }, []);

  const modelCounts = useMemo(() => {
    const configured = providers.filter((provider) => provider.configured).length;
    return { configured, total: providers.length };
  }, [providers]);

  function selectPost(post: GeneratedPostCard, openPreview = true) {
    setSelectedPost(post);
    setPostDraft({
      draft_text: post.draft_text || post.final_text || '',
      final_text: looksLikeInvalidPost(post.final_text) ? '' : post.final_text || '',
      status: post.status || 'draft',
    });
    setSaveState('idle');
    setVisualAssets([]);
    setScheduleError('');
    setScheduleFields(defaultScheduleFields());
    setPreviewEditing(false);
    if (openPreview) setPreviewOpen(true);
  }

  async function saveSelectedPost(nextStatus?: string) {
    if (!selectedPost) return;
    setSaveState('saving');
    try {
      const updated = await api<GeneratedPostCard>(`/api/generated-posts/${selectedPost.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          draft_text: postDraft.draft_text,
          final_text: postDraft.final_text,
          status: nextStatus,
        }),
      });
      selectPost(updated, true);
      setSaveState('saved');
    } catch (err) {
      setActionError(errorMessage(err, t('common.actionError')));
      setSaveState('error');
    }
  }

  async function regenerateSelectedPost(mode = 'regenerate_full') {
    if (!selectedPost) return;
    setSaveState('saving');
    try {
      const updated = await api<GeneratedPostCard>(`/api/generated-posts/${selectedPost.id}/regenerate`, {
        method: 'POST',
        body: JSON.stringify({ use_llm: true, mode }),
      });
      selectPost(updated, true);
      setSaveState('saved');
    } catch (err) {
      setActionError(errorMessage(err, t('common.actionError')));
      setSaveState('error');
    }
  }

  async function regeneratePostCard(post: GeneratedPostCard, mode = 'regenerate_full') {
    selectPost(post, true);
    setSaveState('saving');
    try {
      const updated = await api<GeneratedPostCard>(`/api/generated-posts/${post.id}/regenerate`, {
        method: 'POST',
        body: JSON.stringify({ use_llm: true, mode }),
      });
      selectPost(updated, true);
      setSaveState('saved');
    } catch (err) {
      setActionError(errorMessage(err, t('common.actionError')));
      setSaveState('error');
    }
  }

  async function generateVisualForSelectedPost() {
    if (!selectedPost) return;
    setSaveState('saving');
    try {
      const result = await api<{ asset: PostAsset; post: GeneratedPostCard }>(`/api/generated-posts/${selectedPost.id}/assets/generate`, {
        method: 'POST',
      });
      selectPost(result.post, true);
      setVisualAssets([result.asset]);
      setSaveState('saved');
    } catch (err) {
      setActionError(errorMessage(err, t('common.actionError')));
      setSaveState('error');
    }
  }

  async function loadVisualAssets() {
    if (!selectedPost) return;
    try {
      const data = await api<{ assets: PostAsset[] }>(`/api/generated-posts/${selectedPost.id}/assets`);
      setVisualAssets(data.assets || []);
    } catch (err) {
      setActionError(errorMessage(err, t('common.loadError')));
    }
  }

  async function selectVisualAsset(asset: PostAsset) {
    if (!selectedPost) return;
    setSaveState('saving');
    try {
      const result = await api<{ asset: PostAsset; post: GeneratedPostCard }>(`/api/generated-posts/${selectedPost.id}/assets/${asset.id}/select`, { method: 'PATCH' });
      selectPost(result.post, true);
      await loadVisualAssets();
      setSaveState('saved');
    } catch (err) {
      setActionError(errorMessage(err, t('common.actionError')));
      setSaveState('error');
    }
  }

  async function scheduleSelectedPost() {
    if (!selectedPost) return;
    setSaveState('saving');
    setScheduleError('');
    try {
      let socialAccountId = scheduleAccountId || null;
      if (!socialAccountId && scheduleDestinationName.trim()) {
        const account = await api<SocialAccount>('/api/social-accounts/manual', {
          method: 'POST',
          body: JSON.stringify({
            platform: selectedPost.platform,
            display_name: scheduleDestinationName,
            external_account_id: scheduleDestinationExternalId || null,
            account_url: scheduleDestinationUrl || null,
          }),
        });
        setAccounts((current) => [account, ...current]);
        socialAccountId = account.id;
      }
      const scheduledFor = new Date(`${scheduleFields.date}T${scheduleFields.time || '09:00'}:00`).toISOString();
      const result = await api<{ schedule: ScheduledPost; post: GeneratedPostCard }>(`/api/generated-posts/${selectedPost.id}/schedule`, {
        method: 'POST',
        body: JSON.stringify({
          platform: selectedPost.platform,
          scheduled_for: scheduledFor,
          social_account_id: socialAccountId,
          selected_asset_id: selectedPost.selected_asset?.id || null,
        }),
      });
      selectPost(result.post, true);
      setSaveState('saved');
    } catch (error) {
      const message = error instanceof ApiError ? error.message : t('common.error');
      setScheduleError(message);
      setActionError(message);
      setSaveState('error');
    }
  }

  async function cancelSelectedSchedule() {
    if (!selectedPost?.active_schedule) return;
    setSaveState('saving');
    try {
      await api<ScheduledPost>(`/api/scheduled-posts/${selectedPost.active_schedule.id}/cancel`, { method: 'PATCH' });
      const updated = await api<GeneratedPostCard>(`/api/generated-posts/${selectedPost.id}`);
      selectPost(updated, true);
      setSaveState('saved');
    } catch (err) {
      setActionError(errorMessage(err, t('common.actionError')));
      setSaveState('error');
    }
  }

  async function send(overrideText?: string, overrideContext: Record<string, unknown> = {}) {
    const outgoing = overrideText || text;
    if (!outgoing.trim()) return;
    const optimistic = getOptimisticSteps(outgoing);
    const nextProcessingKey = getProcessingKey(outgoing);
    let tick = 0;
    setSending(true);
    setProgressTick(0);
    setProcessingKey(nextProcessingKey);
    setLongWaitLevel(0);
    setProgressSteps(optimistic);
    const slowTimer = window.setTimeout(() => setLongWaitLevel(1), 8000);
    const verySlowTimer = window.setTimeout(() => setLongWaitLevel(2), 20000);
    const timer = window.setInterval(() => {
      tick += 1;
      setProgressTick(tick);
      setProgressSteps((steps) => {
        const activeIndex = Math.min(tick, Math.max(steps.length - 2, 0));
        return steps.map((step, index) => ({
          ...step,
          status: index < activeIndex ? 'done' : index === activeIndex ? 'active' : 'pending',
        }));
      });
    }, 650);
    try {
      const selectedPostContext = selectedPost
        ? { post_id: selectedPost.id, draft_text: postDraft.draft_text, final_text: postDraft.final_text, post_status: postDraft.status }
        : {};
      const data = await api<{ messages: Message[]; profile: ChatProfile | null; reply?: Message }>('/api/chat', { method: 'POST', body: JSON.stringify({ message: outgoing, context: { ...selectedPostContext, ...overrideContext } }) });
      setMessages(data.messages);
      setProfile(data.profile || null);
      const latestPost = data.reply?.action?.post || data.reply?.action?.posts?.[0] || latestPostFromMessages(data.messages || []);
      if (latestPost) selectPost(latestPost, true);
      if (!overrideText) setText('');
    } catch (err) {
      const message = errorMessage(err, t('common.actionError'));
      setMessages((current) => [
        ...current,
        { role: 'user', text: outgoing },
        { role: 'assistant', text: message, action: { type: 'error', status: 'failed' } },
      ]);
    } finally {
      window.clearInterval(timer);
      window.clearTimeout(slowTimer);
      window.clearTimeout(verySlowTimer);
      setSending(false);
      setProgressSteps([]);
      setLongWaitLevel(0);
    }
  }

  function stepText(step: ChatStep) {
    return step.label || t(`chat.progress.${step.key || 'processing'}`);
  }

  function activeStepText(step: ChatStep) {
    const base = stepText(step).replace(/\.+$/, '');
    return `${base}${'.'.repeat((progressTick % 3) + 1)}`;
  }

  function renderSteps(steps?: ChatStep[]) {
    if (!steps?.length) return null;
    return (
      <div className="chat-stepper">
        {steps.map((step, index) => (
          <div key={`${step.key || step.label}-${index}`} className="chat-step">
            <span className={`chat-step__dot ${step.status === 'done' ? 'is-done' : step.status === 'active' ? 'is-active' : ''}`} />
            <span>{step.status === 'active' ? activeStepText(step) : stepText(step)}</span>
          </div>
        ))}
      </div>
    );
  }

  function getProcessingKey(value: string) {
    const lower = value.toLowerCase();
    if (/(перегенер|передел|заново|короче|экспертнее|живее|человечно|regenerate|rewrite|shorter|expert|human|hook)/i.test(lower)) {
      return 'regenerate';
    }
    if (/(тренд|актуальн.*тем|trend|topic|search|find)/i.test(lower)) {
      return 'trends';
    }
    if (/(контент-план|контент план|план публикац|content plan|plan)/i.test(lower)) {
      return 'plan';
    }
    if (/(пост|post|caption)/i.test(lower)) {
      return 'post';
    }
    if (/(профил|аудитор|цель|тон|платформ|profile|audience|goal|tone|platform)/i.test(lower)) {
      return 'profile';
    }
    return 'answer';
  }

  function processingText() {
    const base = t(`chat.processing.${processingKey}`).replace(/\.+$/, '');
    return `${base}${'.'.repeat((progressTick % 3) + 1)}`;
  }

  function getOptimisticSteps(value: string): ChatStep[] {
    const lower = value.toLowerCase();
    const actionSteps = /(тренд|актуальн.*тем|trend|topic|search|find)/i.test(lower)
      ? ['building_queries', 'searching_materials', 'checking_relevance', 'grouping_trends', 'cleaning_keywords', 'saving_result']
      : /(контент-план|контент план|план публикац|plan)/i.test(lower)
        ? ['loading_trends', 'passing_to_planner', 'creating_content_plan', 'saving_content_plan']
        : /(перегенер|передел|заново|короче|экспертнее|живее|regenerate|rewrite|shorter|expert|human|hook)/i.test(lower)
          ? ['regenerating_post', 'saving_result']
          : /(пост|post|caption)/i.test(lower)
            ? ['generating_post', 'saving_result']
            : /(тон|профил|аудитор|цель|платформ|profile|audience|goal|tone|platform)/i.test(lower)
              ? ['editing_profile', 'saving_result']
              : ['generating_response'];
    return ['analyzing_request', 'loading_profile', ...actionSteps, 'done'].map((key, index) => ({
      key,
      status: index === 0 ? 'active' : 'pending',
    }));
  }

  function createPostFromTrend(trend: TrendCard) {
    send(t('chat.createPostForTrendMessage'), { action: 'generate_post_from_trend', trend_id: trend.id });
  }

  function addTrendToPlan(trend: TrendCard) {
    send(t('chat.addTrendToPlanMessage'), { action: 'add_trend_to_plan', trend_id: trend.id });
  }

  function renderPostWarning() {
    return (
      <div className="chat-warning">
        {t('posts.invalidGeneratedText')}
      </div>
    );
  }

  function renderPostCard(post: GeneratedPostCard) {
    const isSelected = selectedPost?.id === post.id;
    const textValue = isSelected ? postDraft.final_text : post.final_text;
    const invalid = looksLikeInvalidPost(textValue || post.draft_text);
    return (
      <div className="chat-result-card">
        <div className="chat-card-header">
          <div>
            <div className="chat-card-title">{post.platform}</div>
            <div className="chat-card-meta">{post.format} / {status(post.status)}</div>
          </div>
          <button className="secondary-button px-3 py-1 text-xs" type="button" onClick={() => selectPost(post)}>
            {t('chat.editInPreview')}
          </button>
        </div>
        {post.selected_asset?.preview_url ? (
          <img className="chat-post-thumb" src={post.selected_asset.preview_url} alt={post.selected_asset.alt_text || ''} />
        ) : null}
        {invalid ? renderPostWarning() : (
          <ExpandableText
            text={textValue}
            showLabel={t('common.showFull')}
            hideLabel={t('common.collapse')}
            className="generated-post-readable"
          />
        )}
        <div className="chat-actions">
          <button className="secondary-button text-xs" type="button" onClick={() => saveSelectedPost()} disabled={!isSelected || saveState === 'saving' || invalid}>
            <Save size={14} /> {t('common.save')}
          </button>
          <button className="secondary-button text-xs" type="button" onClick={() => regeneratePostCard(post, 'regenerate_full')} disabled={saveState === 'saving'}>
            <RefreshCcw size={14} /> {t('posts.regenerateFull')}
          </button>
          <Link className="secondary-button text-xs" to="/generated-posts">{t('nav.posts')}</Link>
        </div>
      </div>
    );
  }

  function renderTrendCard(trend: TrendCard, index: number) {
    const source = trend.example_source || trend.example_sources?.[0];
    const keywords = (trend.keywords || []).map(cleanKeyword).filter(Boolean).slice(0, 8);
    return (
      <article className="trend-card" key={trend.id || index}>
        <div className="trend-card__top">
          <div>
            <h3>{trend.topic || `${t('chat.trend')} ${index + 1}`}</h3>
            <div className="trend-card__meta">{t('chat.sources')}: {trend.source_count || trend.posts_count || 0}</div>
          </div>
          <div className={`relevance-badge relevance-${trend.relevance_level || 'low'}`}>
            {t(`chat.relevance.${trend.relevance_level || 'low'}`)}
            {typeof trend.relevance_score === 'number' ? <span>{Math.round(trend.relevance_score)}</span> : null}
          </div>
        </div>
        {trend.summary ? <p className="trend-summary">{trend.summary}</p> : null}
        {trend.relevance_reason ? <p className="trend-reason">{trend.relevance_reason}</p> : null}
        {trend.adaptation_suggestion ? <p className="trend-adaptation">{trend.adaptation_suggestion}</p> : null}
        {keywords.length ? (
          <div className="tag-list">
            {keywords.map((keyword) => <span key={keyword} className="tag">{keyword}</span>)}
          </div>
        ) : null}
        {source ? (
          <div className="trend-source">
            {t('chat.exampleSource')}: {source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url}</a> : (source.title || source.source)}
          </div>
        ) : null}
        <div className="chat-actions">
          <button className="secondary-button text-xs" type="button" onClick={() => createPostFromTrend(trend)} disabled={sending}>{t('chat.createPost')}</button>
          <button className="secondary-button text-xs" type="button" onClick={() => addTrendToPlan(trend)} disabled={sending}>{t('chat.addToPlan')}</button>
          <button className="secondary-button text-xs" type="button">{t('chat.more')}</button>
        </div>
      </article>
    );
  }

  function renderTrends(trends?: TrendCard[]) {
    if (!trends?.length) return null;
    const visible = showLowTrends ? trends : trends.filter((trend) => trend.relevance_level !== 'low');
    const hiddenCount = trends.length - visible.length;
    const list = visible.length ? visible : trends.slice(0, 3);
    return (
      <div className="trend-list">
        {list.map((trend, index) => renderTrendCard(trend, index))}
        {hiddenCount > 0 ? (
          <button className="secondary-button text-xs" type="button" onClick={() => setShowLowTrends(true)}>
            {t('chat.showLowRelevance')} ({hiddenCount})
          </button>
        ) : null}
      </div>
    );
  }

  function renderActionRequired(action: ChatAction) {
    if (!action.action_required && !action.status?.startsWith('needs_')) return null;
    return (
      <div className="action-card">
        <div className="chat-card-title">{t('chat.actionNeeded')}</div>
        <div className="chat-actions">
          {action.action_required === 'complete_profile' ? <Link className="secondary-button text-xs" to="/onboarding">{t('onboarding.title')}</Link> : null}
          {action.action_required === 'confirm_profile' ? <Link className="secondary-button text-xs" to="/profile">{t('nav.profile')}</Link> : null}
          {action.action_required === 'find_trends' ? <button className="secondary-button text-xs" type="button" onClick={() => send(t('chat.quickFindTrendsMessage'))}>{t('chat.quickFindTrends')}</button> : null}
          {action.action_required === 'create_content_plan' ? <button className="secondary-button text-xs" type="button" onClick={() => send(t('chat.quickCreatePlanMessage'))}>{t('chat.quickCreatePlan')}</button> : null}
          {action.action_required === 'approve_content_plan' ? <Link className="secondary-button text-xs" to="/content-plans">{t('plan.needsApprovalTitle')}</Link> : null}
          {action.action_required === 'generate_posts' ? <Link className="secondary-button text-xs" to="/content-plans">{t('chat.generatePosts')}</Link> : null}
          {action.action_required === 'review_posts' ? <Link className="secondary-button text-xs" to="/generated-posts">{t('nav.posts')}</Link> : null}
          {action.action_required === 'schedule_posts' ? <Link className="secondary-button text-xs" to="/generated-posts">{t('schedule.schedule')}</Link> : null}
          {action.action_required === 'publish_posts' ? <Link className="secondary-button text-xs" to="/generated-posts">{t('publisher.runDueTelegram')}</Link> : null}
          {action.action_required === 'add_metrics' ? <Link className="secondary-button text-xs" to="/generated-posts">{t('metrics.add')}</Link> : null}
          {action.action_required === 'select_post' ? <Link className="secondary-button text-xs" to="/generated-posts">{t('nav.posts')}</Link> : null}
          {action.action_required === 'select_trend' ? <button className="secondary-button text-xs" type="button" onClick={() => send(t('chat.quickShowTrendsMessage'))}>{t('chat.trend')}</button> : null}
        </div>
      </div>
    );
  }

  function renderAction(action?: ChatAction) {
    if (!action || !action.type) return null;
    if (!action.run_summary && !action.trends?.length && !action.summary && !action.items?.length && !action.post && !action.posts?.length && !action.action_required && !action.status?.startsWith('needs_')) return null;
    return (
      <div className="chat-action-stack">
        {renderActionRequired(action)}
        {action.run_summary ? (
          <div className="chat-result-card">
            <div className="chat-card-title">{t('chat.runSummary')}</div>
            <div className="chat-card-meta">
              {t('chat.rawPostsFound')}: {action.run_summary.raw_posts_found || 0} / {t('chat.trendsFound')}: {action.run_summary.trends_found || 0}
            </div>
            {(action.run_summary.queries_used || []).length ? (
              <div className="tag-list">
                {(action.run_summary.queries_used || []).slice(0, 4).map((query) => <span className="tag" key={query}>{query}</span>)}
              </div>
            ) : null}
          </div>
        ) : null}
        {renderTrends(action.trends)}
        {action.summary ? (
          <div className="chat-result-card">
            <div className="section-label">{t('chat.planSummary')}</div>
            <div className="chat-card-title">{action.summary.direction}</div>
            <div className="summary-grid">
              <div><span>{t('chat.planAudience')}</span>{action.summary.audience || '-'}</div>
              <div><span>{t('chat.planGoal')}</span>{action.summary.goal || '-'}</div>
            </div>
            {action.summary.platforms?.length ? (
              <div className="tag-list">{action.summary.platforms.map((platform) => <span key={platform} className="tag">{platform}</span>)}</div>
            ) : null}
            {action.summary.content_pillars?.length ? (
              <div className="tag-list">{action.summary.content_pillars.map((pillar) => <span key={pillar} className="tag tag-accent">{pillar}</span>)}</div>
            ) : null}
            <div className="chat-actions">
              <Link className="secondary-button text-xs" to={action.plan?.id ? `/content-plans/${action.plan.id}` : '/content-plans'}>{t('chat.openPlan')}</Link>
              <Link className="secondary-button text-xs" to="/generated-posts">{t('chat.generatePosts')}</Link>
            </div>
          </div>
        ) : null}
        {action.items?.length ? (
          <div className="chat-action-stack">
            {action.items.slice(0, 5).map((item, index) => (
              <div key={item.id || index} className="chat-result-card compact">
                <div className="chat-card-title">{index + 1}. {item.platform} / {item.format}</div>
                <div className="chat-card-meta">{item.scheduled_date} {String(item.scheduled_time || '').slice(0, 5)}</div>
                <div className="muted-text">{item.post_idea || '-'}</div>
              </div>
            ))}
          </div>
        ) : null}
        {action.post ? renderPostCard(action.post) : null}
        {action.posts?.length ? <div className="chat-action-stack">{action.posts.slice(0, 3).map((post) => renderPostCard(post))}</div> : null}
      </div>
    );
  }

  function renderPreviewPanel() {
    const invalid = looksLikeInvalidPost(postDraft.final_text || selectedPost?.final_text);
    return (
      <aside className={`chat-preview panel ${previewOpen ? 'is-open' : ''}`}>
        <div className="chat-panel-title">
          <div>
            <div className="section-label">{t('chat.previewTitle')}</div>
            <div className="muted-text">{selectedPost ? `${selectedPost.platform} / ${selectedPost.format}` : t('chat.previewEmpty')}</div>
          </div>
          <button className="icon-button lg:hidden" type="button" onClick={() => setPreviewOpen(false)} title={t('common.close')}>
            <X size={16} />
          </button>
        </div>
        {!selectedPost ? (
          <div className="empty-state">{t('chat.previewEmpty')}</div>
        ) : (
          <div className="preview-stack">
            <div className="social-preview">
              <div className="social-preview__head">
                <div>
                  <div className="social-preview__author">{profile?.name || t('profile.unnamed')}</div>
                  <div className="chat-card-meta">{selectedPost.platform}</div>
                </div>
                <div className="preview-head-actions">
                  <span className="status-pill">{status(postDraft.status)}</span>
                  <button className="secondary-button text-xs" type="button" onClick={() => setPreviewEditing((current) => !current)}>
                    {previewEditing ? t('common.previewMode') : t('chat.editInPreview')}
                  </button>
                </div>
              </div>
              {selectedPost.selected_asset?.preview_url ? (
                <img className="social-preview__image" src={selectedPost.selected_asset.preview_url} alt={selectedPost.selected_asset.alt_text || t('chat.previewImagePlaceholder')} />
              ) : (
                <div className="social-preview__placeholder">{selectedPost.selected_asset?.image_prompt || t('chat.previewImagePlaceholder')}</div>
              )}
              <div className="field-help">{t('posts.finalHelp')}</div>
              {invalid ? renderPostWarning() : (
                previewEditing ? (
                  <textarea
                    className="field social-preview__text"
                    value={postDraft.final_text}
                    onChange={(event) => {
                      setPostDraft((current) => ({ ...current, final_text: event.target.value }));
                      setSaveState('unsaved');
                    }}
                  />
                ) : (
                  <ExpandableText
                    text={postDraft.final_text}
                    showLabel={t('common.showFull')}
                    hideLabel={t('common.collapse')}
                    className="preview-readable-text"
                  />
                )
              )}
              {selectedPost.active_schedule ? <div className="chat-card-meta">{t('schedule.active')}: {formatLocalDateTime(selectedPost.active_schedule.scheduled_for)}</div> : null}
            </div>
            <label className="form-label">
              {t('posts.draftText')}
              <span className="field-help">{t('posts.draftHelp')}</span>
              {previewEditing ? (
                <textarea
                  className="field min-h-28 chat-draft-textarea"
                  value={postDraft.draft_text}
                  onChange={(event) => {
                    setPostDraft((current) => ({ ...current, draft_text: event.target.value }));
                    setSaveState('unsaved');
                  }}
                />
              ) : (
                <ExpandableText
                  text={postDraft.draft_text}
                  showLabel={t('common.showFull')}
                  hideLabel={t('common.collapse')}
                  className="preview-readable-text is-draft"
                />
              )}
            </label>
            <select
              className="field"
              value={postDraft.status}
              onChange={(event) => {
                setPostDraft((current) => ({ ...current, status: event.target.value }));
                setSaveState('unsaved');
              }}
            >
              {POST_STATUSES.map((value) => <option key={value} value={value}>{status(value)}</option>)}
            </select>
            <div className="schedule-box">
              <div className="section-label">{t('schedule.title')}</div>
              <div className="form-grid">
                <select className="field" value={scheduleAccountId} onChange={(event) => setScheduleAccountId(event.target.value)}>
                  <option value="">{t('schedule.noDestination')}</option>
                  {accounts
                    .filter((account) => account.platform.toLowerCase() === selectedPost.platform.toLowerCase())
                    .map((account) => <option key={account.id} value={account.id}>{account.display_name}</option>)}
                </select>
                {!scheduleAccountId ? (
                  <>
                    <input className="field" value={scheduleDestinationName} onChange={(event) => setScheduleDestinationName(event.target.value)} placeholder={t('schedule.destinationName')} />
                    <input className="field" value={scheduleDestinationExternalId} onChange={(event) => setScheduleDestinationExternalId(event.target.value)} placeholder={selectedPost.platform.toLowerCase() === 'telegram' ? t('schedule.telegramExternalId') : t('schedule.destinationId')} />
                    <input className="field" value={scheduleDestinationUrl} onChange={(event) => setScheduleDestinationUrl(event.target.value)} placeholder={t('schedule.destinationUrl')} />
                  </>
                ) : null}
                <div className="form-grid form-grid--2">
                  <input className="field" type="date" value={scheduleFields.date} onChange={(event) => setScheduleFields((current) => ({ ...current, date: event.target.value }))} />
                  <input className="field" type="time" value={scheduleFields.time} onChange={(event) => setScheduleFields((current) => ({ ...current, time: event.target.value }))} />
                </div>
              </div>
              <div className="chat-card-meta">{t('schedule.timezoneNote')}</div>
              {scheduleError ? <div className="chat-error">{scheduleError}</div> : null}
              {!SCHEDULABLE_STATUSES.has(selectedPost.status) ? <div className="chat-warning">{t('schedule.requiresApproval')}</div> : null}
            </div>
            <div className="preview-actions">
              <button className="secondary-button text-xs" type="button" onClick={() => saveSelectedPost()} disabled={saveState === 'saving' || invalid}>
                <Save size={14} /> {t('common.save')}
              </button>
              <button className="secondary-button text-xs" type="button" onClick={() => saveSelectedPost('approved')} disabled={saveState === 'saving' || invalid}>
                <Check size={14} /> {t('common.approve')}
              </button>
              <button className="secondary-button text-xs" type="button" onClick={() => regenerateSelectedPost('regenerate_full')} disabled={saveState === 'saving'}>
                <RefreshCcw size={14} /> {t('posts.regenerateFull')}
              </button>
              <button className="secondary-button text-xs" type="button" onClick={() => regenerateSelectedPost('improve_current')} disabled={saveState === 'saving'}>
                {t('posts.improveFinal')}
              </button>
              <button className="secondary-button text-xs" type="button" onClick={() => regenerateSelectedPost('shorter')} disabled={saveState === 'saving'}>
                {t('posts.makeShorter')}
              </button>
              {selectedPost.active_schedule ? (
                <button className="secondary-button text-xs" type="button" onClick={cancelSelectedSchedule} disabled={saveState === 'saving'}>
                  <CalendarClock size={14} /> {t('schedule.cancel')}
                </button>
              ) : (
                <button className="secondary-button text-xs" type="button" onClick={scheduleSelectedPost} disabled={saveState === 'saving' || !SCHEDULABLE_STATUSES.has(selectedPost.status) || invalid}>
                  <CalendarClock size={14} /> {t('schedule.schedule')}
                </button>
              )}
              <button className="secondary-button text-xs" type="button" onClick={generateVisualForSelectedPost} disabled={saveState === 'saving'}>
                {selectedPost.selected_asset ? t('visual.regenerate') : t('visual.generate')}
              </button>
              <button className="secondary-button text-xs" type="button" onClick={loadVisualAssets} disabled={saveState === 'saving'}>
                {t('visual.select')}
              </button>
            </div>
            {visualAssets.length ? (
              <div className="asset-grid">
                {visualAssets.map((asset) => (
                  <button key={asset.id} className={`asset-card ${asset.is_selected ? 'is-selected' : ''}`} type="button" onClick={() => selectVisualAsset(asset)}>
                    {asset.preview_url ? <img src={asset.preview_url} alt={asset.alt_text || ''} /> : null}
                    <div className="chat-card-title">{t('visual.idea')}</div>
                    <div className="chat-card-meta">{asset.search_query || asset.image_prompt || '-'}</div>
                  </button>
                ))}
              </div>
            ) : null}
            <div className="save-state">
              {saveState === 'unsaved' ? t('common.unsaved') : saveState === 'saving' ? t('common.saving') : saveState === 'saved' ? t('common.saved') : saveState === 'error' ? t('common.error') : ''}
            </div>
          </div>
        )}
      </aside>
    );
  }

  function renderSidebar() {
    return (
      <aside className={`chat-sidebar panel ${sidebarOpen ? 'is-open' : ''}`}>
        <div className="chat-panel-title">
          <div>
            <div className="section-label">{t('chat.sidebar')}</div>
            <div className="muted-text">{t('chat.ideas')}</div>
          </div>
          <button className="icon-button lg:hidden" type="button" onClick={() => setSidebarOpen(false)} title={t('common.close')}><X size={16} /></button>
        </div>
        <div className="sidebar-card">
          <div className="section-label">{t('chat.clientInfo')}</div>
          {profile ? (
            <dl className="profile-summary">
              <div><dt>{t('profile.name')}</dt><dd>{profile.name || '-'}</dd></div>
              <div><dt>{t('profile.niche')}</dt><dd>{profile.niche || '-'}</dd></div>
              <div><dt>{t('profile.profession')}</dt><dd>{profile.profession || '-'}</dd></div>
              <div><dt>{t('profile.goal')}</dt><dd>{profile.goal || '-'}</dd></div>
              <div><dt>{t('chat.planAudience')}</dt><dd>{profile.audience || '-'}</dd></div>
              <div><dt>{t('profile.platforms')}</dt><dd>{(profile.platforms || []).join(', ') || '-'}</dd></div>
            </dl>
          ) : (
            <div className="empty-state">{t('chat.noProfile')}</div>
          )}
        </div>
        <div className="sidebar-card">
          <div className="section-label">{t('chat.models')}</div>
          <div className="model-summary">{modelCounts.configured}/{modelCounts.total || 4} {t('chat.configured')}</div>
          <div className="model-list">
            {providers.map((provider) => (
              <div key={provider.id} className="model-row">
                <span>{provider.name}</span>
                <span className={`model-badge ${provider.configured ? 'is-on' : ''}`}>{provider.configured ? t('chat.configured') : t('chat.notConfigured')}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="sidebar-card">
          <div className="section-label">{t('chat.quickActions')}</div>
          <div className="quick-actions">
            <button className="secondary-button text-xs" type="button" onClick={() => send(t('chat.quickFindTrendsMessage'))}>{t('chat.quickFindTrends')}</button>
            <button className="secondary-button text-xs" type="button" onClick={() => send(t('chat.quickCreatePlanMessage'))}>{t('chat.quickCreatePlan')}</button>
            <button className="secondary-button text-xs" type="button" onClick={() => send(t('chat.quickRecommendationsMessage'))}>{t('chat.quickRecommendations')}</button>
            <Link className="secondary-button text-xs" to="/profile">{t('nav.profile')}</Link>
          </div>
        </div>
      </aside>
    );
  }

  function renderMessage(message: Message, index: number) {
    const cleanedText = message.role === 'assistant' ? cleanAssistantText(message.text) : message.text;
    const hasAction = Boolean(message.action);
    if (!cleanedText && !hasAction) return null;
    return (
      <div key={index} className={`message-row ${message.role === 'user' ? 'is-user' : 'is-assistant'}`}>
        <div className="message-bubble">
          {cleanedText ? (
            message.role === 'assistant' && cleanedText.length > 520 ? (
              <ExpandableText
                text={cleanedText}
                showLabel={t('common.showFull')}
                hideLabel={t('common.collapse')}
                className="message-text expandable-message-text"
              />
            ) : (
              <div className="message-text">{cleanedText}</div>
            )
          ) : null}
          {message.role === 'assistant' ? renderAction(message.action) : null}
        </div>
      </div>
    );
  }

  return (
    <>
      {actionError ? <div className="chat-error page-error">{actionError}</div> : null}
      <div className="chat-mobile-tabs">
        <button className="secondary-button" type="button" onClick={() => setSidebarOpen((value) => !value)}>{t('chat.sidebar')}</button>
        <button className="secondary-button" type="button" onClick={() => setPreviewOpen((value) => !value)}>{t('chat.previewTitle')}</button>
      </div>
      <div className="chat-workspace">
        {renderSidebar()}
        <section className="chat-center panel">
          <div className="chat-center__head">
            <div>
              <div className="section-label">{t('nav.chat')}</div>
              <div className="muted-text">{t('chat.desc')}</div>
            </div>
            <Sparkles size={20} />
          </div>
          <div className="chat-scroll">
            {messages.length === 0 ? <div className="empty-state">{t('common.empty')}</div> : null}
            {messages.map((message, index) => renderMessage(message, index))}
            {sending ? (
              <div className="message-row is-assistant">
                <div className="message-bubble">
                  <div className="message-text">
                    {progressSteps.find((step) => step.status === 'active') ? activeStepText(progressSteps.find((step) => step.status === 'active') as ChatStep) : t('common.loading')}
                  </div>
                  {renderSteps(progressSteps)}
                </div>
              </div>
            ) : null}
          </div>
          {sending ? (
            <div className="chat-live-status" role="status" aria-live="polite">
              <span className="chat-live-status__pulse" />
              <div>
                <div className="chat-live-status__title">{processingText()}</div>
                {longWaitLevel === 1 ? <div className="chat-live-status__hint">{t('chat.processing.slowHint')}</div> : null}
                {longWaitLevel >= 2 ? <div className="chat-live-status__hint">{t('chat.processing.verySlowHint')}</div> : null}
              </div>
            </div>
          ) : null}
          <div className="chat-inputbar">
            <textarea
              className="field chat-input"
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  send();
                }
              }}
              placeholder={t('chat.inputPlaceholder')}
              disabled={sending}
            />
            <button className={`icon-button send-button ${sending ? 'is-loading' : ''}`} onClick={() => send()} title={t('common.send')} disabled={sending} aria-busy={sending}>
              {sending ? <span className="button-spinner" /> : <Send size={18} />}
            </button>
          </div>
        </section>
        {renderPreviewPanel()}
      </div>
    </>
  );
}
