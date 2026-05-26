import { useEffect, useState } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatCard } from '../components/StatCard';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';

export default function ProfileAnalyticsPage() {
  const { t } = useI18n();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  async function load() {
    setError('');
    try {
      setData(await api('/api/analytics/profile'));
    } catch (err) {
      setError(errorMessage(err, t('common.loadError')));
    }
  }
  useEffect(() => {
    load();
  }, []);
  const completeness = data?.completeness || 0;
  const chart = [
    { name: 'Complete', value: completeness },
    { name: 'Missing', value: 100 - completeness },
  ];
  return (
    <>
      <PageHeader title={t('profileAnalytics.title')} description={t('profileAnalytics.desc')} />
      <ErrorNotice message={error} onRetry={load} />
      <div className="grid gap-4 lg:grid-cols-3">
        <StatCard label={t('profileAnalytics.completeness')} value={`${completeness}%`} accent="teal" />
        <StatCard label={t('profileAnalytics.tone')} value={data?.tone || '-'} accent="grape" />
        <StatCard label={t('profileAnalytics.platforms')} value={(data?.platforms || []).length} accent="amber" />
      </div>
      <div className="panel mt-4 grid gap-4 p-5 lg:grid-cols-2">
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie data={chart} dataKey="value" innerRadius={70} outerRadius={100}>
              <Cell fill="#0f766e" />
              <Cell fill="#e85d4f" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div>
          <h2 className="text-lg font-bold">{t('profileAnalytics.missing')}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {(data?.missing || []).map((field: string) => (
              <span key={field} className="bg-coral/10 px-3 py-1 text-sm text-coral" style={{ borderRadius: 8 }}>{field}</span>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
