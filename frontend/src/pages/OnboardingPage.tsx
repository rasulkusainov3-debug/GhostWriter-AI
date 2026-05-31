import { ArrowRight, CheckCircle2, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorNotice } from '../components/ErrorNotice';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';

type Question = { key: string; text: string; choices?: string[]; example?: string };
type Answers = Record<string, string>;

function isOptionalPlatformQuestion(question: Question) {
  const source = `${question.key} ${question.text}`.toLowerCase();
  return /(platform|publish|social|соцсет|публиков|платформ|telegram|linkedin|instagram)/i.test(source);
}

function usesTextarea(question: Question) {
  const source = `${question.key} ${question.text}`.toLowerCase();
  return /(audience|goal|values|avoid|content|links|аудитор|цель|ценност|избег|контент|ссылк|опис)/i.test(source);
}

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { lang, t } = useI18n();
  const [sessionId, setSessionId] = useState('');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Answers>({});
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
      setAnswers((current) => {
        const next = { ...current };
        data.questions.forEach((question) => {
          if (next[question.key] === undefined) next[question.key] = '';
        });
        return next;
      });
    } catch (err) {
      setError(errorMessage(err, t('common.loadError')));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    start();
  }, []);

  const requiredQuestions = useMemo(() => questions.filter((question) => !isOptionalPlatformQuestion(question)), [questions]);
  const filledCount = questions.filter((question) => answers[question.key]?.trim()).length;
  const requiredFilled = requiredQuestions.every((question) => answers[question.key]?.trim());
  const pct = questions.length ? Math.round((filledCount / questions.length) * 100) : 0;
  const optionalLabel = lang === 'en' ? 'Optional' : lang === 'kz' ? 'Қосымша' : 'Необязательно';

  function updateAnswer(key: string, value: string) {
    setAnswers((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!sessionId || finishing) return;
    if (!requiredFilled) {
      setError(t('auth.errors.VALIDATION_ERROR'));
      return;
    }
    setError('');
    setFinishing(true);
    try {
      for (const question of questions) {
        const answer = answers[question.key]?.trim();
        if (!answer) continue;
        await api(`/api/onboarding/${sessionId}/answers`, { method: 'POST', body: JSON.stringify({ key: question.key, answer }) });
      }
      const result = await api<{ flow?: Array<{ step: string; status: string; count?: number }> }>(`/api/onboarding/${sessionId}/finish`, { method: 'POST' });
      const trends = result.flow?.find((item) => item.step === 'trends_found');
      setSummary(`${t('chat.progress.profile_saved')}. ${t('chat.trendsFound')}: ${trends?.count ?? 0}`);
      navigate('/chat');
    } catch (err) {
      setError(errorMessage(err, t('common.actionError')));
      setFinishing(false);
    }
  }

  return (
    <section className="onboarding-page">
      <div className="onboarding-shell">
        <header className="onboarding-hero reveal-section">
          <div>
            <div className="onboarding-pill">
              <Sparkles size={15} />
              <span>Digital profile builder</span>
            </div>
            <h1>{t('onboarding.title')}</h1>
            <p>{t('onboarding.desc')}</p>
          </div>
          <aside className="onboarding-summary-card">
            <span>{filledCount}/{questions.length || 9}</span>
            <strong>{t('dashboard.profile.title')}</strong>
            <p>{t('landing.feature1.text')}</p>
            <div className="onboarding-progress">
              <i style={{ width: `${pct}%` }} />
            </div>
          </aside>
        </header>

        <ErrorNotice message={error} onRetry={loading || finishing ? undefined : start} />

        <form className="onboarding-form reveal-section" onSubmit={submit}>
          {loading ? <div className="onboarding-loading">{t('common.loading')}</div> : null}
          {summary ? <div className="onboarding-success">{summary}</div> : null}

          {finishing ? (
            <div className="onboarding-finish">
              {finishSteps.map((key) => (
                <div key={key}>
                  <span />
                  <p>{t(`chat.progress.${key}`)}</p>
                </div>
              ))}
            </div>
          ) : null}

          <div className="onboarding-question-grid">
            {questions.map((question, index) => {
              const value = answers[question.key] || '';
              const optional = isOptionalPlatformQuestion(question);
              const longAnswer = usesTextarea(question);
              return (
                <article key={question.key} className={`onboarding-question-card ${longAnswer ? 'is-wide' : ''}`}>
                  <div className="onboarding-question-card__top">
                    <span>{index + 1}</span>
                    {optional ? <em>{optionalLabel}</em> : null}
                  </div>
                  <h2>{question.text}</h2>
                  {question.example ? <p>{question.example}</p> : null}

                  {question.choices ? (
                    <div className="onboarding-choice-list">
                      {question.choices.map((choice) => (
                        <button
                          key={choice}
                          className={value === choice ? 'is-selected' : ''}
                          onClick={() => updateAnswer(question.key, choice)}
                          type="button"
                        >
                          <CheckCircle2 size={16} />
                          {choice}
                        </button>
                      ))}
                    </div>
                  ) : longAnswer ? (
                    <textarea
                      className="field onboarding-field onboarding-textarea"
                      disabled={finishing}
                      value={value}
                      onChange={(event) => updateAnswer(question.key, event.target.value)}
                    />
                  ) : (
                    <input
                      className="field onboarding-field"
                      disabled={finishing}
                      value={value}
                      onChange={(event) => updateAnswer(question.key, event.target.value)}
                    />
                  )}
                </article>
              );
            })}
          </div>

          <footer className="onboarding-actions">
            <div>
              <strong>{filledCount}/{questions.length || 9}</strong>
              <span>{t('onboarding.desc')}</span>
            </div>
            <button className="primary-button onboarding-submit" type="submit" disabled={!requiredFilled || !sessionId || finishing || loading}>
              {finishing ? t('onboarding.loading.button') : t('common.finish')} <ArrowRight size={16} />
            </button>
          </footer>
        </form>
      </div>

      {finishing ? (
        <div className="onboarding-loading-overlay" role="status" aria-live="polite">
          <div className="onboarding-loading-modal">
            <div className="onboarding-loading-spinner" />
            <h2 className="onboarding-loading-title">{t('onboarding.loading.title')}</h2>
            <p className="onboarding-loading-text">{t('onboarding.loading.text')}</p>
            <div className="onboarding-loading-steps">
              <div className="onboarding-loading-step">
                <span />
                {t('onboarding.loading.step1')}
              </div>
              <div className="onboarding-loading-step">
                <span />
                {t('onboarding.loading.step2')}
              </div>
              <div className="onboarding-loading-step">
                <span />
                {t('onboarding.loading.step3')}
              </div>
            </div>
            <div className="onboarding-loading-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
