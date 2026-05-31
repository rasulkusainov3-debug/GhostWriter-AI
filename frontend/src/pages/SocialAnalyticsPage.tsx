import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Activity,
  BarChart3,
  Database,
  ExternalLink,
  Flame,
  Globe2,
  Link2,
  RefreshCcw,
  TrendingUp,
  UsersRound,
} from 'lucide-react';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';

type SourceRow = {
  source?: string;
  count?: number | string;
  avg_score?: number | string;
};

type RawTopic = {
  title?: string;
  score?: number | string;
  comments?: number | string;
  url?: string;
};

type TrendRow = {
  id?: number;
  topic?: string;
  summary?: string;
  keywords?: string[] | string;
  final_score?: number | string;
  posts_count?: number | string;
  source_count?: number | string;
  generated_posts_count?: number | string;
  scheduled_posts_count?: number | string;
  published_posts_count?: number | string;
  feedback_signal?: string;
};

type SocialAnalytics = {
  by_source?: SourceRow[];
  top_topics?: RawTopic[];
};

type TrendAnalytics = {
  total?: number;
  active?: number;
  expired?: number;
  top?: TrendRow[];
};

type SocialAccountsAnalytics = {
  total_accounts?: number;
  platform_distribution?: Array<{ platform?: string; count?: number | string }>;
  scheduled_posts_per_platform?: Array<{ platform?: string; status?: string; count?: number | string }>;
  metrics_missing?: boolean;
};

const LABELS = {
  ru: {
    refresh: 'Обновить',
    overview: 'Обзор источников',
    rawMaterials: 'Сырые материалы',
    activeTrends: 'Активные тренды',
    accounts: 'Соцаккаунты',
    topTrend: 'Главный тренд',
    sourceMap: 'Карта источников',
    sourceMapText: 'Сколько материалов пришло из каждого канала и насколько сильный у них сигнал.',
    source: 'Источник',
    materials: 'материалов',
    averageSignal: 'средний сигнал',
    manualOnly: 'Только ручные метрики',
    manualOnlyText: 'Внешние метрики платформ пока не подключены. Здесь показаны внутренние данные: парсинг, тренды, источники и ручные метрики.',
    connectedPlatforms: 'Подключенные платформы',
    publishingQueue: 'Публикации по платформам',
    noAccounts: 'Соцаккаунты пока не добавлены',
    noSchedule: 'Запланированных публикаций пока нет',
    topMaterials: 'Топ материалов',
    topMaterialsText: 'Исходные материалы, которые сильнее всего повлияли на пул тем.',
    topTrends: 'Тренды в работе',
    topTrendsText: 'Активные темы, из которых можно создавать планы и посты.',
    openSource: 'Открыть источник',
    score: 'сигнал',
    comments: 'комментарии',
    sources: 'источники',
    posts: 'материалы',
    generated: 'посты',
    scheduled: 'запланировано',
    published: 'опубликовано',
    emptySources: 'Источники появятся после поиска трендов.',
    emptyMaterials: 'Материалы появятся после парсинга и поиска трендов.',
    emptyTrends: 'Активные тренды пока не найдены.',
    noTopTrend: 'Пока нет активного тренда',
  },
  en: {
    refresh: 'Refresh',
    overview: 'Source overview',
    rawMaterials: 'Raw materials',
    activeTrends: 'Active trends',
    accounts: 'Social accounts',
    topTrend: 'Top trend',
    sourceMap: 'Source map',
    sourceMapText: 'How many materials came from each channel and how strong their signal is.',
    source: 'Source',
    materials: 'materials',
    averageSignal: 'average signal',
    manualOnly: 'Manual metrics only',
    manualOnlyText: 'External platform metrics are not connected yet. This page shows internal data: parsing, trends, sources, and manual metrics.',
    connectedPlatforms: 'Connected platforms',
    publishingQueue: 'Publishing by platform',
    noAccounts: 'No social accounts yet',
    noSchedule: 'No scheduled publishing yet',
    topMaterials: 'Top materials',
    topMaterialsText: 'Source materials that had the strongest influence on the topic pool.',
    topTrends: 'Trends in progress',
    topTrendsText: 'Active topics ready for plans and post generation.',
    openSource: 'Open source',
    score: 'signal',
    comments: 'comments',
    sources: 'sources',
    posts: 'materials',
    generated: 'posts',
    scheduled: 'scheduled',
    published: 'published',
    emptySources: 'Sources will appear after trend search.',
    emptyMaterials: 'Materials will appear after parsing and trend search.',
    emptyTrends: 'No active trends found yet.',
    noTopTrend: 'No active top trend yet',
  },
  kz: {
    refresh: 'Жаңарту',
    overview: 'Дереккөздер шолуы',
    rawMaterials: 'Шикі материалдар',
    activeTrends: 'Белсенді трендтер',
    accounts: 'Әлеуметтік аккаунттар',
    topTrend: 'Басты тренд',
    sourceMap: 'Дереккөз картасы',
    sourceMapText: 'Әр арнадан қанша материал келді және олардың сигналы қаншалықты күшті.',
    source: 'Дереккөз',
    materials: 'материал',
    averageSignal: 'орташа сигнал',
    manualOnly: 'Тек қолмен енгізілген метрикалар',
    manualOnlyText: 'Платформалардың сыртқы метрикалары әзірше қосылмаған. Мұнда ішкі деректер көрсетіледі: парсинг, трендтер, дереккөздер және қолмен енгізілген метрикалар.',
    connectedPlatforms: 'Қосылған платформалар',
    publishingQueue: 'Платформа бойынша жариялау',
    noAccounts: 'Әлеуметтік аккаунттар әлі қосылмаған',
    noSchedule: 'Жоспарланған жарияланымдар жоқ',
    topMaterials: 'Үздік материалдар',
    topMaterialsText: 'Тақырыптар пулына ең көп әсер еткен бастапқы материалдар.',
    topTrends: 'Жұмыстағы трендтер',
    topTrendsText: 'Жоспар мен пост жасауға дайын белсенді тақырыптар.',
    openSource: 'Дереккөзді ашу',
    score: 'сигнал',
    comments: 'пікірлер',
    sources: 'дереккөздер',
    posts: 'материалдар',
    generated: 'посттар',
    scheduled: 'жоспарланған',
    published: 'жарияланған',
    emptySources: 'Дереккөздер тренд іздеуден кейін пайда болады.',
    emptyMaterials: 'Материалдар парсинг пен тренд іздеуден кейін пайда болады.',
    emptyTrends: 'Белсенді трендтер әлі табылған жоқ.',
    noTopTrend: 'Әзірше басты тренд жоқ',
  },
};

function asNumber(value: unknown) {
  const next = Number(value || 0);
  return Number.isFinite(next) ? next : 0;
}

function formatNumber(value: unknown) {
  return new Intl.NumberFormat().format(Math.round(asNumber(value)));
}

function toList(value: unknown) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === 'string') return value.split(',').map((item) => item.trim()).filter(Boolean);
  return [];
}

function StatTile({ icon: Icon, label, value, accent = 'cyan' }: { icon: typeof Database; label: string; value: string | number; accent?: 'cyan' | 'orange' | 'green' | 'violet' }) {
  return (
    <article className={`social-stat-tile social-stat-tile--${accent}`}>
      <div className="social-stat-tile__icon"><Icon size={22} /></div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="social-analytics-empty">{text}</div>;
}

export default function SocialAnalyticsPage() {
  const { t, lang, status } = useI18n();
  const labels = LABELS[lang] || LABELS.ru;
  const compactLabels = {
    showAll: lang === 'en' ? 'Show all' : lang === 'kz' ? 'Барлығын көрсету' : 'Показать все',
    hide: lang === 'en' ? 'Hide' : lang === 'kz' ? 'Жасыру' : 'Скрыть',
    details: lang === 'en' ? 'Details' : lang === 'kz' ? 'Толығырақ' : 'Подробнее',
    close: lang === 'en' ? 'Close' : lang === 'kz' ? 'Жабу' : 'Закрыть',
    materialDetails: lang === 'en' ? 'Material details' : lang === 'kz' ? 'Материал деректері' : 'Детали материала',
    trendDetails: lang === 'en' ? 'Trend details' : lang === 'kz' ? 'Тренд деректері' : 'Детали тренда',
    summary: lang === 'en' ? 'Summary' : lang === 'kz' ? 'Сипаттама' : 'Описание',
    keywords: lang === 'en' ? 'Keywords' : lang === 'kz' ? 'Кілт сөздер' : 'Ключевые слова',
  };
  const [data, setData] = useState<SocialAnalytics>({ by_source: [], top_topics: [] });
  const [trends, setTrends] = useState<TrendAnalytics>({ total: 0, active: 0, top: [] });
  const [accounts, setAccounts] = useState<SocialAccountsAnalytics>({ total_accounts: 0, platform_distribution: [] });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAllMaterials, setShowAllMaterials] = useState(false);
  const [showAllTrends, setShowAllTrends] = useState(false);
  const [selectedMaterial, setSelectedMaterial] = useState<RawTopic | null>(null);
  const [selectedTrend, setSelectedTrend] = useState<TrendRow | null>(null);

  async function load() {
    setError('');
    setLoading(true);
    const [socialResult, trendsResult, accountsResult] = await Promise.allSettled([
      api<SocialAnalytics>('/api/analytics/social'),
      api<TrendAnalytics>('/api/analytics/trends'),
      api<SocialAccountsAnalytics>('/api/analytics/social-accounts'),
    ]);
    if (socialResult.status === 'fulfilled') setData(socialResult.value);
    else setError(errorMessage(socialResult.reason, t('common.loadError')));
    if (trendsResult.status === 'fulfilled') setTrends(trendsResult.value);
    if (accountsResult.status === 'fulfilled') setAccounts(accountsResult.value);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  function closeDetails() {
    setSelectedMaterial(null);
    setSelectedTrend(null);
  }

  useEffect(() => {
    if (!selectedMaterial && !selectedTrend) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeDetails();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedMaterial, selectedTrend]);

  const sourceRows = data.by_source || [];
  const materialRows = data.top_topics || [];
  const trendRows = trends.top || [];
  const visibleMaterials = showAllMaterials ? materialRows : materialRows.slice(0, 5);
  const visibleTrends = showAllTrends ? trendRows : trendRows.slice(0, 5);
  const rawPostsCount = sourceRows.reduce((sum, item) => sum + asNumber(item.count), 0);
  const chartData = useMemo(
    () => sourceRows.map((item) => ({
      source: item.source || '-',
      count: asNumber(item.count),
      avg_score: Math.round(asNumber(item.avg_score)),
    })),
    [sourceRows],
  );
  const maxTopicScore = Math.max(1, ...materialRows.map((item) => asNumber(item.score)));
  const maxTrendScore = Math.max(1, ...trendRows.map((item) => asNumber(item.final_score)));
  const topTrend = trends.top?.[0];
  const scheduleRows = accounts.scheduled_posts_per_platform || [];
  const selectedTrendKeywords = toList(selectedTrend?.keywords);

  return (
    <div className="social-analytics-page">
      <PageHeader
        title={t('social.title')}
        description={t('social.desc')}
        action={(
          <button className="secondary-button social-refresh-button" type="button" onClick={load} disabled={loading}>
            <RefreshCcw size={17} /> {labels.refresh}
          </button>
        )}
      />
      <ErrorNotice message={error} onRetry={load} />

      <section className="social-analytics-hero">
        <div>
          <div className="section-label">{labels.overview}</div>
          <h2>{topTrend?.topic || labels.noTopTrend}</h2>
          <p>{topTrend?.summary || labels.manualOnlyText}</p>
        </div>
        <div className="social-analytics-note">
          <SparklineIcon />
          <strong>{labels.manualOnly}</strong>
          <span>{labels.manualOnlyText}</span>
        </div>
      </section>

      <div className="social-stat-grid">
        <StatTile icon={Database} label={labels.rawMaterials} value={formatNumber(rawPostsCount)} accent="cyan" />
        <StatTile icon={TrendingUp} label={labels.activeTrends} value={formatNumber(trends.active || 0)} accent="orange" />
        <StatTile icon={UsersRound} label={labels.accounts} value={formatNumber(accounts.total_accounts || 0)} accent="green" />
        <StatTile icon={Flame} label={labels.topTrend} value={topTrend ? formatNumber(topTrend.final_score) : '-'} accent="violet" />
      </div>

      <div className="social-analytics-grid">
        <section className="social-analytics-card social-analytics-card--chart">
          <div className="social-card-head">
            <div>
              <span className="section-label">{labels.sourceMap}</span>
              <h2>{labels.sourceMap}</h2>
              <p>{labels.sourceMapText}</p>
            </div>
            <BarChart3 size={25} />
          </div>
          {chartData.length ? (
            <div className="social-chart-wrap">
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={chartData} margin={{ top: 12, right: 12, bottom: 8, left: -12 }}>
                  <defs>
                    <linearGradient id="socialSourceFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#ff7a38" />
                      <stop offset="100%" stopColor="#0f766e" />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(255,247,237,0.12)" strokeDasharray="4 6" vertical={false} />
                  <XAxis dataKey="source" stroke="rgba(255,247,237,0.58)" tickLine={false} axisLine={false} />
                  <YAxis stroke="rgba(255,247,237,0.58)" tickLine={false} axisLine={false} />
                  <Tooltip
                    cursor={{ fill: 'rgba(255,247,237,0.05)' }}
                    contentStyle={{
                      background: 'rgba(10, 14, 16, 0.94)',
                      border: '1px solid rgba(255,255,255,0.14)',
                      borderRadius: 14,
                      color: '#fff7ed',
                    }}
                  />
                  <Bar dataKey="count" fill="url(#socialSourceFill)" radius={[12, 12, 4, 4]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState text={labels.emptySources} />
          )}
          <div className="social-source-list">
            {chartData.map((item) => (
              <div key={item.source} className="social-source-row">
                <div>
                  <strong>{item.source}</strong>
                  <span>{formatNumber(item.count)} {labels.materials}</span>
                </div>
                <em>{labels.averageSignal}: {formatNumber(item.avg_score)}</em>
              </div>
            ))}
          </div>
        </section>

        <aside className="social-analytics-stack">
          <section className="social-analytics-card">
            <div className="social-card-head social-card-head--compact">
              <div>
                <span className="section-label">{labels.connectedPlatforms}</span>
                <h2>{labels.connectedPlatforms}</h2>
              </div>
              <Globe2 size={24} />
            </div>
            {(accounts.platform_distribution || []).length ? (
              <div className="social-platform-list">
                {(accounts.platform_distribution || []).map((item) => (
                  <div key={item.platform || 'platform'} className="social-platform-chip">
                    <span>{item.platform || '-'}</span>
                    <strong>{formatNumber(item.count)}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState text={labels.noAccounts} />
            )}
          </section>

          <section className="social-analytics-card">
            <div className="social-card-head social-card-head--compact">
              <div>
                <span className="section-label">{labels.publishingQueue}</span>
                <h2>{labels.publishingQueue}</h2>
              </div>
              <Activity size={24} />
            </div>
            {scheduleRows.length ? (
              <div className="social-schedule-list">
                {scheduleRows.map((item) => (
                  <div key={`${item.platform}-${item.status}`} className="social-schedule-row">
                    <span>{item.platform || '-'}</span>
                    <b>{status(item.status) || item.status || '-'}</b>
                    <strong>{formatNumber(item.count)}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState text={labels.noSchedule} />
            )}
          </section>
        </aside>
      </div>

      <div className="social-lists-grid">
        <section className="social-analytics-card">
          <div className="social-card-head">
            <div>
              <span className="section-label">{labels.topMaterials}</span>
              <h2>{labels.topMaterials}</h2>
              <p>{labels.topMaterialsText}</p>
            </div>
            <div className="social-section-actions">
              {materialRows.length > 5 ? (
                <button className="secondary-button social-list-toggle" type="button" onClick={() => setShowAllMaterials((value) => !value)}>
                  {showAllMaterials ? compactLabels.hide : `${compactLabels.showAll} ${materialRows.length}`}
                </button>
              ) : null}
              <Link2 size={24} />
            </div>
          </div>
          <div className="social-ranked-list">
            {materialRows.length === 0 ? <EmptyState text={labels.emptyMaterials} /> : null}
            {visibleMaterials.map((item, index) => {
              const score = asNumber(item.score);
              const rank = materialRows.indexOf(item) + 1 || index + 1;
              return (
                <article key={item.url || item.title || index} className="social-ranked-item social-ranked-item--compact">
                  <span className="social-rank">{String(rank).padStart(2, '0')}</span>
                  <div className="social-ranked-item__body">
                    <strong>{item.title || '-'}</strong>
                    <div className="social-ranked-meta">
                      <span>{labels.score}: {formatNumber(score)}</span>
                      <span>{labels.comments}: {formatNumber(item.comments)}</span>
                    </div>
                    <div className="social-progress"><i style={{ width: `${Math.max(4, Math.min(100, (score / maxTopicScore) * 100))}%` }} /></div>
                    <div className="social-card-actions">
                      <button className="social-details-button" type="button" onClick={() => setSelectedMaterial(item)}>{compactLabels.details}</button>
                      {item.url ? (
                        <a href={item.url} target="_blank" rel="noreferrer" className="social-details-button social-details-button--link">
                          {labels.openSource} <ExternalLink size={14} />
                        </a>
                      ) : null}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="social-analytics-card">
          <div className="social-card-head">
            <div>
              <span className="section-label">{labels.topTrends}</span>
              <h2>{labels.topTrends}</h2>
              <p>{labels.topTrendsText}</p>
            </div>
            <div className="social-section-actions">
              {trendRows.length > 5 ? (
                <button className="secondary-button social-list-toggle" type="button" onClick={() => setShowAllTrends((value) => !value)}>
                  {showAllTrends ? compactLabels.hide : `${compactLabels.showAll} ${trendRows.length}`}
                </button>
              ) : null}
              <TrendingUp size={24} />
            </div>
          </div>
          <div className="social-ranked-list social-ranked-list--trends">
            {trendRows.length === 0 ? <EmptyState text={labels.emptyTrends} /> : null}
            {visibleTrends.map((item, index) => {
              const score = asNumber(item.final_score);
              const rank = trendRows.indexOf(item) + 1 || index + 1;
              return (
                <article key={item.id || item.topic || index} className="social-ranked-item">
                  <span className="social-rank">{String(rank).padStart(2, '0')}</span>
                  <div className="social-ranked-item__body">
                    <strong>{item.topic || '-'}</strong>
                    {item.summary ? <p>{item.summary}</p> : null}
                    <div className="social-ranked-meta">
                      <span>{labels.sources}: {formatNumber(item.source_count)}</span>
                      <span>{labels.posts}: {formatNumber(item.posts_count)}</span>
                      <span>{labels.generated}: {formatNumber(item.generated_posts_count)}</span>
                      <span>{labels.scheduled}: {formatNumber(item.scheduled_posts_count)}</span>
                      <span>{labels.published}: {formatNumber(item.published_posts_count)}</span>
                    </div>
                    <div className="social-progress"><i style={{ width: `${Math.max(4, Math.min(100, (score / maxTrendScore) * 100))}%` }} /></div>
                    <div className="social-card-actions">
                      <button className="social-details-button" type="button" onClick={() => setSelectedTrend(item)}>{compactLabels.details}</button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </div>

      {(selectedMaterial || selectedTrend) ? (
        <div className="social-details-backdrop" role="presentation" onClick={closeDetails}>
          <section
            className="social-details-modal"
            role="dialog"
            aria-modal="true"
            aria-label={selectedTrend ? compactLabels.trendDetails : compactLabels.materialDetails}
            onClick={(event) => event.stopPropagation()}
          >
            <button className="social-details-close" type="button" onClick={closeDetails}>{compactLabels.close}</button>
            {selectedTrend ? (
              <>
                <span className="section-label">{compactLabels.trendDetails}</span>
                <h2>{selectedTrend.topic || '-'}</h2>
                <div className="social-details-meta">
                  <span>{labels.score}: {formatNumber(selectedTrend.final_score)}</span>
                  <span>{labels.sources}: {formatNumber(selectedTrend.source_count)}</span>
                  <span>{labels.posts}: {formatNumber(selectedTrend.posts_count)}</span>
                  <span>{labels.generated}: {formatNumber(selectedTrend.generated_posts_count)}</span>
                  <span>{labels.scheduled}: {formatNumber(selectedTrend.scheduled_posts_count)}</span>
                  <span>{labels.published}: {formatNumber(selectedTrend.published_posts_count)}</span>
                </div>
                {selectedTrend.summary ? (
                  <div className="social-details-section">
                    <h3>{compactLabels.summary}</h3>
                    <p>{selectedTrend.summary}</p>
                  </div>
                ) : null}
                {selectedTrendKeywords.length ? (
                  <div className="social-details-section">
                    <h3>{compactLabels.keywords}</h3>
                    <div className="social-details-tags">
                      {selectedTrendKeywords.map((keyword) => <span key={keyword}>{keyword}</span>)}
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
            {selectedMaterial ? (
              <>
                <span className="section-label">{compactLabels.materialDetails}</span>
                <h2>{selectedMaterial.title || '-'}</h2>
                <div className="social-details-meta">
                  <span>{labels.score}: {formatNumber(selectedMaterial.score)}</span>
                  <span>{labels.comments}: {formatNumber(selectedMaterial.comments)}</span>
                </div>
                {selectedMaterial.url ? (
                  <a href={selectedMaterial.url} target="_blank" rel="noreferrer" className="primary-button social-details-source">
                    {labels.openSource} <ExternalLink size={16} />
                  </a>
                ) : null}
              </>
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}

function SparklineIcon() {
  return (
    <svg aria-hidden="true" className="social-sparkline-icon" viewBox="0 0 44 44">
      <path d="M7 28h6l5-12 7 18 6-11h6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
      <circle cx="31" cy="23" r="3" fill="currentColor" />
    </svg>
  );
}
