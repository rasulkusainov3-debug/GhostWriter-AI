import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import {
  BarChart3,
  CheckCircle2,
  FileText,
  Image as ImageIcon,
  MessageCircle,
  Send,
  Sparkles,
  Target,
  UserRound,
  UsersRound,
} from 'lucide-react';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';

type ProfileAnalytics = {
  completeness: number;
  missing: string[];
  profile?: {
    name?: string;
    niche?: string;
    profession?: string;
    goal?: string;
    tone?: string;
    audience?: string;
    avoid?: string;
    user_values?: string[];
    platforms?: string[];
  } | null;
  style?: {
    voice?: string;
    writing_style?: string;
    preferred_structure?: string[];
    vocabulary_preferences?: string[];
    avoid_phrases?: string[];
    example_post_ids?: string[];
  };
  activity?: {
    active_trends?: number;
    generated_posts?: number;
    selected_visuals?: number;
    published_posts?: number;
    metrics_rows?: number;
  };
  recommendations?: string[];
  platforms?: string[];
  values?: string[];
  tone?: string;
};

const LABELS = {
  ru: {
    ready: 'Профиль готов к генерации контента',
    needsWork: 'Профиль нужно дополнить',
    profileSummary: 'Сводка профиля',
    toneVoice: 'Тон и голос',
    audience: 'Аудитория',
    platforms: 'Платформы',
    values: 'Ценности',
    avoid: 'Что избегать',
    style: 'Индивидуальный стиль',
    structure: 'Структура',
    vocabulary: 'Предпочтения по словам',
    styleExamples: 'Примеры стиля',
    recommendations: 'Рекомендации',
    connectedData: 'Связанные данные',
    trends: 'Активные тренды',
    posts: 'Посты',
    visuals: 'Визуалы',
    publications: 'Публикации',
    metrics: 'Метрики',
    missingFields: 'Что ещё заполнить',
    empty: 'Нет данных',
    examplesSuffix: 'шт.',
    fieldNames: {
      name: 'имя',
      niche: 'ниша',
      profession: 'профессия',
      goal: 'цель',
      tone: 'тон',
      audience: 'аудитория',
      avoid: 'ограничения',
      user_values: 'ценности',
      platforms: 'платформы',
      personality: 'индивидуальный стиль',
      profile: 'профиль',
    } as Record<string, string>,
  },
  en: {
    ready: 'Profile is ready for content generation',
    needsWork: 'Profile needs more detail',
    profileSummary: 'Profile summary',
    toneVoice: 'Tone and voice',
    audience: 'Audience',
    platforms: 'Platforms',
    values: 'Values',
    avoid: 'Avoid',
    style: 'Individual style',
    structure: 'Structure',
    vocabulary: 'Vocabulary preferences',
    styleExamples: 'Style examples',
    recommendations: 'Recommendations',
    connectedData: 'Connected data',
    trends: 'Active trends',
    posts: 'Posts',
    visuals: 'Visuals',
    publications: 'Publications',
    metrics: 'Metrics',
    missingFields: 'Missing fields',
    empty: 'No data',
    examplesSuffix: 'items',
    fieldNames: {
      name: 'name',
      niche: 'niche',
      profession: 'profession',
      goal: 'goal',
      tone: 'tone',
      audience: 'audience',
      avoid: 'avoid list',
      user_values: 'values',
      platforms: 'platforms',
      personality: 'individual style',
      profile: 'profile',
    } as Record<string, string>,
  },
  kz: {
    ready: 'Профиль контент жасауға дайын',
    needsWork: 'Профильді толықтыру керек',
    profileSummary: 'Профиль қысқаша',
    toneVoice: 'Тон және дауыс',
    audience: 'Аудитория',
    platforms: 'Платформалар',
    values: 'Құндылықтар',
    avoid: 'Неден аулақ болу керек',
    style: 'Жеке стиль',
    structure: 'Құрылым',
    vocabulary: 'Сөз таңдауы',
    styleExamples: 'Стиль мысалдары',
    recommendations: 'Ұсынымдар',
    connectedData: 'Байланысты деректер',
    trends: 'Белсенді трендтер',
    posts: 'Посттар',
    visuals: 'Визуалдар',
    publications: 'Жарияланымдар',
    metrics: 'Метрикалар',
    missingFields: 'Толтыру керек өрістер',
    empty: 'Деректер жоқ',
    examplesSuffix: 'дана',
    fieldNames: {
      name: 'аты',
      niche: 'ниша',
      profession: 'мамандық',
      goal: 'мақсат',
      tone: 'тон',
      audience: 'аудитория',
      avoid: 'шектеулер',
      user_values: 'құндылықтар',
      platforms: 'платформалар',
      personality: 'жеке стиль',
      profile: 'профиль',
    } as Record<string, string>,
  },
};

function toArray(value: unknown): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === 'string') return value.split(/[;,]/).map((item) => item.trim()).filter(Boolean);
  return [];
}

function TagList({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <span className="profile-analytics-empty">{empty}</span>;
  return (
    <div className="profile-analytics-tags">
      {items.map((item) => <span key={item}>{item}</span>)}
    </div>
  );
}

export default function ProfileAnalyticsPage() {
  const { t, lang } = useI18n();
  const l = LABELS[lang] || LABELS.ru;
  const [data, setData] = useState<ProfileAnalytics | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setError('');
    setLoading(true);
    try {
      setData(await api('/api/analytics/profile'));
    } catch (err) {
      setError(errorMessage(err, t('common.loadError')));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const profile = data?.profile || {};
  const style = data?.style || {};
  const activity = data?.activity || {};
  const completeness = Math.max(0, Math.min(100, Number(data?.completeness || 0)));
  const platforms = toArray(profile.platforms || data?.platforms);
  const values = toArray(profile.user_values || data?.values);
  const avoidItems = toArray(profile.avoid).concat(toArray(style.avoid_phrases)).filter((item, index, list) => list.indexOf(item) === index);
  const audienceTags = useMemo(() => {
    const text = profile.audience || '';
    return text.split(/[,\n]/).map((item) => item.trim()).filter(Boolean).slice(0, 8);
  }, [profile.audience]);
  const missing = (data?.missing || []).map((field) => l.fieldNames[field] || field);
  const scoreStyle = { '--profile-score': `${completeness}%` } as CSSProperties;
  const completionStatus = completeness >= 80 ? l.ready : l.needsWork;
  const activityCards = [
    { label: l.trends, value: activity.active_trends || 0, icon: Target },
    { label: l.posts, value: activity.generated_posts || 0, icon: FileText },
    { label: l.visuals, value: activity.selected_visuals || 0, icon: ImageIcon },
    { label: l.publications, value: activity.published_posts || 0, icon: Send },
    { label: l.metrics, value: activity.metrics_rows || 0, icon: BarChart3 },
  ];

  return (
    <div className="profile-analytics-page">
      <PageHeader title={t('profileAnalytics.title')} description={t('profileAnalytics.desc')} />
      <ErrorNotice message={error} onRetry={load} />
      {loading ? <div className="panel profile-analytics-loading">{t('common.loading')}</div> : null}
      {!loading ? (
        <>
          <section className="profile-analytics-grid">
            <article className="profile-analytics-card profile-analytics-card--hero">
              <div className="profile-analytics-card__heading">
                <div>
                  <span className="profile-analytics-kicker">{t('profileAnalytics.completeness')}</span>
                  <h2>{completeness}%</h2>
                  <p>{completionStatus}</p>
                </div>
                <div className="profile-analytics-donut" style={scoreStyle}>
                  <span>{completeness}%</span>
                </div>
              </div>
              <div className="profile-analytics-summary">
                <div>
                  <span>{l.profileSummary}</span>
                  <strong>{profile.name || l.empty}</strong>
                  <p>{[profile.profession, profile.niche, profile.goal].filter(Boolean).join(' · ') || l.empty}</p>
                </div>
              </div>
            </article>

            <article className="profile-analytics-card">
              <div className="profile-analytics-title-row">
                <Sparkles />
                <div>
                  <h2>{l.toneVoice}</h2>
                  <p>{style.voice || profile.tone || l.empty}</p>
                </div>
              </div>
              <div className="profile-analytics-divider" />
              <h3>{l.style}</h3>
              <p className="profile-analytics-text">{style.writing_style || l.empty}</p>
              <div className="profile-analytics-mini-grid">
                <div>
                  <span>{l.structure}</span>
                  <TagList items={toArray(style.preferred_structure)} empty={l.empty} />
                </div>
                <div>
                  <span>{l.vocabulary}</span>
                  <TagList items={toArray(style.vocabulary_preferences)} empty={l.empty} />
                </div>
              </div>
            </article>
          </section>

          <section className="profile-analytics-grid profile-analytics-grid--secondary">
            <article className="profile-analytics-card">
              <div className="profile-analytics-title-row">
                <UsersRound />
                <div>
                  <h2>{l.audience}</h2>
                  <p>{profile.audience || l.empty}</p>
                </div>
              </div>
              <TagList items={audienceTags} empty={l.empty} />
            </article>

            <article className="profile-analytics-card">
              <div className="profile-analytics-title-row">
                <MessageCircle />
                <div>
                  <h2>{l.recommendations}</h2>
                  <p>{completeness >= 80 ? l.ready : l.needsWork}</p>
                </div>
              </div>
              <ul className="profile-analytics-list">
                {(data?.recommendations || []).map((item) => <li key={item}>{item}</li>)}
              </ul>
            </article>
          </section>

          <section className="profile-analytics-card profile-analytics-card--wide">
            <div className="profile-analytics-title-row">
              <CheckCircle2 />
              <div>
                <h2>{l.platforms}</h2>
                <p>{platforms.length ? platforms.join(' · ') : l.empty}</p>
              </div>
            </div>
            <div className="profile-analytics-columns">
              <div>
                <h3>{l.platforms}</h3>
                <TagList items={platforms} empty={l.empty} />
              </div>
              <div>
                <h3>{l.values}</h3>
                <TagList items={values} empty={l.empty} />
              </div>
              <div>
                <h3>{l.avoid}</h3>
                <TagList items={avoidItems} empty={l.empty} />
              </div>
            </div>
          </section>

          <section className="profile-analytics-activity">
            {activityCards.map(({ label, value, icon: Icon }) => (
              <article className="profile-analytics-activity-card" key={label}>
                <Icon />
                <span>{label}</span>
                <strong>{value}</strong>
              </article>
            ))}
          </section>

          <section className="profile-analytics-card profile-analytics-card--wide">
            <div className="profile-analytics-title-row">
              <UserRound />
              <div>
                <h2>{l.missingFields}</h2>
                <p>{missing.length ? l.needsWork : l.ready}</p>
              </div>
            </div>
            <TagList items={missing} empty={l.ready} />
            <p className="profile-analytics-footnote">
              {l.styleExamples}: {toArray(style.example_post_ids).length} {l.examplesSuffix}
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}
