import { ArrowRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';

type Question = { key: string; text: string; choices?: string[]; example?: string };

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [sessionId, setSessionId] = useState('');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [finishing, setFinishing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState('');
  const finishSteps = ['profile_saved', 'searching_trends', 'analyzing_trends', 'trends_saved'];

  async function start() {
    setLoading(true);
    setError('');
    try {
      const data = await api<{ session: { id: string }; questions: Question[] }>('/api/onboarding/start', { method: 'POST' });
      setSessionId(data.session.id);
      setQuestions(data.questions);
    } catch (err) {
      setError(errorMessage(err, t('common.loadError')));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    start();
  }, []);

  async function next() {
    const question = questions[index];
    if (!question || !answer.trim()) return;
    setError('');
    try {
      await api(`/api/onboarding/${sessionId}/answers`, { method: 'POST', body: JSON.stringify({ key: question.key, answer }) });
      setAnswer('');
      if (index + 1 >= questions.length) {
        setFinishing(true);
        const result = await api<{ flow?: Array<{ step: string; status: string; count?: number }> }>(`/api/onboarding/${sessionId}/finish`, { method: 'POST' });
        const trends = result.flow?.find((item) => item.step === 'trends_found');
        setSummary(`${t('chat.progress.profile_saved')}. ${t('chat.trendsFound')}: ${trends?.count ?? 0}`);
        navigate('/chat');
      } else {
        setIndex(index + 1);
      }
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
      setFinishing(false);
    }
  }

  const question = questions[index];
  const pct = questions.length ? Math.round(((index + 1) / questions.length) * 100) : 0;

  return (
    <>
      <PageHeader title={t('onboarding.title')} description={t('onboarding.desc')} />
      <ErrorNotice message={error} onRetry={loading || finishing ? undefined : start} />
      <section className="panel mx-auto max-w-2xl p-6">
        {loading ? <div className="text-sm text-black/50">{t('common.loading')}</div> : null}
        {summary ? <div className="mb-4 rounded-md border border-teal/20 bg-teal/10 p-3 text-sm font-semibold text-teal">{summary}</div> : null}
        <div className="mb-5 h-2 overflow-hidden bg-black/5" style={{ borderRadius: 8 }}>
          <div className="h-full bg-teal transition-all" style={{ width: `${pct}%` }} />
        </div>
        {finishing ? (
          <div className="mb-5 grid gap-2 border border-black/10 bg-black/5 p-3 text-sm text-black/65" style={{ borderRadius: 8 }}>
            {finishSteps.map((key) => (
              <div key={key} className="flex items-center gap-2">
                <span className="h-2 w-2 animate-pulse rounded-full bg-teal" />
                <span>{t(`chat.progress.${key}`)}</span>
              </div>
            ))}
          </div>
        ) : null}
        <div className="min-h-72">
          <div className="text-sm font-semibold text-black/50">
            {t('onboarding.question')} {Math.min(index + 1, questions.length || 1)} / {questions.length || 1}
          </div>
          <h2 className="mt-4 text-2xl font-bold">{question?.text || t('common.loading')}</h2>
          {question?.example ? <p className="mt-2 text-sm text-black/50">{question.example}</p> : null}
          {question?.choices ? (
            <div className="mt-6 grid gap-2">
              {question.choices.map((choice) => (
                <button key={choice} className={answer === choice ? 'primary-button justify-start' : 'secondary-button justify-start'} onClick={() => setAnswer(choice)}>
                  {choice}
                </button>
              ))}
            </div>
          ) : (
            <textarea className="field mt-6 min-h-32" value={answer} onChange={(e) => setAnswer(e.target.value)} />
          )}
        </div>
        <button className="primary-button mt-5" onClick={next} disabled={!answer.trim() || !sessionId || finishing}>
          {index + 1 >= questions.length ? t('common.finish') : t('common.next')} <ArrowRight size={16} />
        </button>
      </section>
    </>
  );
}
