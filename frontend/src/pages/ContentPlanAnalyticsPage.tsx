import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatCard } from '../components/StatCard';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';

export default function ContentPlanAnalyticsPage() {
  const { planId } = useParams();
  const { t } = useI18n();
  const [data, setData] = useState<any>({ breakdown: [] });
  const [summary, setSummary] = useState<any>(null);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    const [planResult, summaryResult] = await Promise.allSettled([
      planId ? api(`/api/content-plans/${planId}/analytics`) : Promise.resolve({ breakdown: [] }),
      api('/api/analytics/content-plans'),
    ]);
    if (planResult.status === 'fulfilled') setData(planResult.value);
    else setError(errorMessage(planResult.reason, t('common.loadError')));
    if (summaryResult.status === 'fulfilled') setSummary(summaryResult.value);
    else setSummary(null);
  }

  useEffect(() => {
    load();
  }, [planId]);

  const total = useMemo(() => (data.breakdown || []).reduce((sum: number, item: any) => sum + Number(item.count || 0), 0), [data]);
  const platforms = new Set((data.breakdown || []).map((item: any) => item.platform)).size;
  const manualMetrics = data.manual_metrics || summary?.manual_metrics || {};
  const bestPlatform = manualMetrics.best_platforms?.[0];
  const bestFormat = manualMetrics.best_formats?.[0];

  return (
    <>
      <PageHeader title={t('planAnalytics.title')} description={t('planAnalytics.desc')} />
      <ErrorNotice message={error} onRetry={load} />
      <div className="grid gap-4 lg:grid-cols-3">
        <StatCard label={t('analytics.planItems')} value={total} accent="teal" />
        <StatCard label={t('profile.platforms')} value={platforms} accent="grape" />
        <StatCard label={t('analytics.totalPlans')} value={summary?.total_plans || 0} accent="amber" />
        <StatCard label={t('analytics.generatedPosts')} value={summary?.generated_post_count || 0} accent="teal" />
        <StatCard label={t('analytics.readyPosts')} value={summary?.approved_scheduled_published_count || 0} accent="grape" />
        <StatCard label={t('analytics.totalItems')} value={summary?.total_items || 0} accent="amber" />
        <StatCard label={t('metrics.manualRows')} value={manualMetrics.metrics_rows || manualMetrics.rows || 0} accent="teal" />
        <StatCard label={t('metrics.avgEngagement')} value={`${Number(manualMetrics.average_engagement_rate || 0).toFixed(2)}%`} accent="grape" />
      </div>
      <section className="panel mt-4 p-5">
        <div className="mb-2 text-xs font-semibold uppercase tracking-normal text-black/50">{t('recommendations.basedOnManual')}</div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-md border border-black/10 bg-white p-3 text-sm text-black/65">
            <b>{t('recommendations.bestPlatform')}:</b> {bestPlatform?.platform || '-'}
            {bestPlatform ? <span className="ml-2 text-black/45">{Number(bestPlatform.average_engagement_rate || 0).toFixed(2)}%</span> : null}
          </div>
          <div className="rounded-md border border-black/10 bg-white p-3 text-sm text-black/65">
            <b>{t('recommendations.bestFormat')}:</b> {bestFormat?.format || '-'}
            {bestFormat ? <span className="ml-2 text-black/45">{Number(bestFormat.average_engagement_rate || 0).toFixed(2)}%</span> : null}
          </div>
        </div>
      </section>
      <div className="panel mt-4 p-5">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data.breakdown || []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="platform" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#6d5bd0" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}
