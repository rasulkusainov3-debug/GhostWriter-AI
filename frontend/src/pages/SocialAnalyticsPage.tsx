import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatCard } from '../components/StatCard';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';

export default function SocialAnalyticsPage() {
  const { t } = useI18n();
  const [data, setData] = useState<any>({ by_source: [], top_topics: [] });
  const [trends, setTrends] = useState<any>({ total: 0, active: 0, top: [] });
  const [accounts, setAccounts] = useState<any>({ total_accounts: 0, platform_distribution: [] });
  const [error, setError] = useState('');
  async function load() {
    setError('');
    const [socialResult, trendsResult, accountsResult] = await Promise.allSettled([
      api('/api/analytics/social'),
      api('/api/analytics/trends'),
      api('/api/analytics/social-accounts'),
    ]);
    if (socialResult.status === 'fulfilled') setData(socialResult.value);
    else setError(errorMessage(socialResult.reason, t('common.loadError')));
    if (trendsResult.status === 'fulfilled') setTrends(trendsResult.value);
    if (accountsResult.status === 'fulfilled') setAccounts(accountsResult.value);
  }
  useEffect(() => {
    load();
  }, []);
  const rawPostsCount = (data.by_source || []).reduce((sum: number, item: any) => sum + Number(item.count || 0), 0);
  const topTrend = trends.top?.[0]?.topic || '-';
  return (
    <>
      <PageHeader title={t('social.title')} description={t('social.desc')} />
      <ErrorNotice message={error} onRetry={load} />
      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t('analytics.rawPosts')} value={rawPostsCount} accent="teal" />
        <StatCard label={t('analytics.activeTrends')} value={trends.active || 0} accent="grape" />
        <StatCard label={t('analytics.socialAccounts')} value={accounts.total_accounts || 0} accent="amber" />
        <StatCard label={t('analytics.topTrend')} value={topTrend} accent="teal" />
      </div>
      <div className="panel mb-4 p-4 text-sm text-black/60">{t('metrics.manualOnly')}. {t('analytics.metricsMissingNotice')}</div>
      <div className="panel p-5">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data.by_source || []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="source" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#0f766e" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <section className="panel mt-4 p-5">
        <h2 className="text-lg font-bold">{t('social.top')}</h2>
        <div className="mt-4 space-y-3">
          {(data.top_topics || []).length === 0 ? <div className="text-sm text-black/50">{t('common.empty')}</div> : null}
          {(data.top_topics || []).map((item: any) => (
            <a key={item.url || item.title} href={item.url} className="block border-b border-black/10 pb-3 text-sm hover:text-teal">
              {item.title || '-'} <span className="text-black/40">score {item.score || 0}</span>
            </a>
          ))}
        </div>
      </section>
    </>
  );
}
