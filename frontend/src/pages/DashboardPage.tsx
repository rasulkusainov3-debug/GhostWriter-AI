import { ArrowRight, BarChart3, FileClock, FileText, MessageSquareText, PenLine, UserRound, UsersRound } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatCard } from '../components/StatCard';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';
import type { RecommendationsResponse } from '../types';

export default function DashboardPage() {
  const { t } = useI18n();
  const [analytics, setAnalytics] = useState<any>(null);
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    const [analyticsResult, recommendationsResult] = await Promise.allSettled([
      api('/api/analytics/dashboard'),
      api<RecommendationsResponse>('/api/analytics/recommendations'),
    ]);
    if (analyticsResult.status === 'fulfilled') setAnalytics(analyticsResult.value);
    else setError(errorMessage(analyticsResult.reason, t('common.loadError')));
    if (recommendationsResult.status === 'fulfilled') setRecommendations(recommendationsResult.value);
    else setRecommendations(null);
  }

  useEffect(() => {
    load();
  }, []);

  const generatedTotal = useMemo(
    () => Object.values(analytics?.generated_posts_by_status || {}).reduce((sum: number, value: any) => sum + Number(value || 0), 0),
    [analytics],
  );
  const scheduledTotal = useMemo(
    () => Object.values(analytics?.scheduled_posts_by_status || {}).reduce((sum: number, value: any) => sum + Number(value || 0), 0),
    [analytics],
  );
  const assetCoverage = analytics?.asset_coverage || {};
  const manualMetrics = analytics?.manual_metrics || {};
  const visualCoverage = `${assetCoverage.posts_with_selected_visual || 0}/${assetCoverage.total_posts || 0}`;
  const topTrend = analytics?.top_trends?.[0]?.topic || '-';

  const cards = [
    { to: '/chat', title: t('nav.chat'), text: t('dashboard.chat.text'), icon: MessageSquareText },
    { to: '/profile', title: t('nav.profile'), text: t('dashboard.profile.text'), icon: UserRound },
    { to: '/history', title: t('nav.history'), text: t('dashboard.history.text'), icon: FileClock },
    { to: '/content-plans', title: t('nav.plans'), text: t('dashboard.plans.text'), icon: PenLine },
    { to: '/generated-posts', title: t('nav.posts'), text: t('posts.desc'), icon: FileText },
    { to: '/analytics/profile', title: t('nav.profileAnalytics'), text: t('dashboard.profileAnalytics.text'), icon: BarChart3 },
    { to: '/analytics/social', title: t('nav.socialAnalytics'), text: t('dashboard.social.text'), icon: UsersRound },
    { to: '/content-plans', title: t('planAnalytics.title'), text: t('planAnalytics.desc'), icon: BarChart3 },
  ];

  const recommendationState = !recommendations
    ? t('common.loading')
    : recommendations.data_quality === 'limited'
      ? t('recommendations.preliminary')
      : recommendations.data_quality === 'none'
        ? t('recommendations.notEnough')
        : t('recommendations.basedOnManual');

  return (
    <>
      <PageHeader title={t('dashboard.title')} description={t('dashboard.desc')} />
      <ErrorNotice message={error} onRetry={load} />

      <div className="menu-grid dashboard-menu-grid">
        {cards.map(({ to, title, text, icon: Icon }) => (
          <Link key={`${to}-${title}`} to={to} className="menu-card panel">
            <span className="menu-card__icon"><Icon size={21} /></span>
            <div>
              <h2 className="menu-card__title">{title}</h2>
              <p className="menu-card__text">{text}</p>
            </div>
            <span className="menu-card__cta">{t('common.open')} <ArrowRight size={14} /></span>
          </Link>
        ))}
      </div>

      <div className="stat-grid">
        <StatCard label={t('analytics.profileCompleteness')} value={`${analytics?.profile_completeness || 0}%`} accent="teal" />
        <StatCard label={t('analytics.generatedPosts')} value={generatedTotal} accent="grape" />
        <StatCard label={t('analytics.scheduledPosts')} value={scheduledTotal} accent="amber" />
        <StatCard label={t('analytics.publishedPosts')} value={analytics?.published_schedules_count || 0} accent="teal" />
        <StatCard label={t('analytics.failedSchedules')} value={analytics?.failed_schedules_count || 0} accent="coral" />
        <StatCard label={t('analytics.visualCoverage')} value={visualCoverage} accent="amber" />
        <StatCard label={t('analytics.activeTrends')} value={analytics?.trends_count || 0} accent="grape" />
        <StatCard label={t('analytics.trendRuns')} value={analytics?.trend_runs_count || 0} accent="teal" />
        <StatCard label={t('metrics.manualRows')} value={manualMetrics.rows || 0} accent="amber" />
        <StatCard label={t('metrics.avgEngagement')} value={`${Number(manualMetrics.average_engagement_rate || 0).toFixed(2)}%`} accent="grape" />
      </div>

      <section className="section-panel panel">
        <div className="dashboard-split">
          <div>
            <div className="section-label">{t('analytics.topTrend')}</div>
            <div className="section-title">{topTrend}</div>
          </div>
          <div className="muted-text">
            {t('metrics.manualOnly')}. {t('analytics.metricsMissingNotice')}
          </div>
        </div>
      </section>

      <section className="section-panel panel">
        <div className="work-card__header">
          <div>
            <div className="section-label">{t('recommendations.title')}</div>
            <div className="muted-text">{t('recommendations.basedOnManual')}</div>
          </div>
          <span className="status-pill">{recommendationState}</span>
        </div>
        {recommendations?.data_quality === 'none' ? (
          <p className="muted-text">{t('recommendations.notEnough')}</p>
        ) : (
          <div className="dashboard-split">
            <ul className="muted-text space-y-2">
              {(recommendations?.recommendations || []).slice(0, 4).map((item) => <li key={item}>{item}</li>)}
            </ul>
            <div className="muted-text space-y-2">
              <div><b>{t('recommendations.bestPlatform')}:</b> {recommendations?.best_platforms?.[0]?.platform || '-'}</div>
              <div><b>{t('recommendations.nextActions')}:</b> {(recommendations?.next_actions || []).slice(0, 2).join(' / ') || '-'}</div>
            </div>
          </div>
        )}
      </section>

    </>
  );
}
