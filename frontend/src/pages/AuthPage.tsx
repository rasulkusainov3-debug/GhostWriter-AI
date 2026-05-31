import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, Sparkles } from 'lucide-react';
import { LanguageSwitcher } from '../components/LanguageSwitcher';
import { ApiError, api, clearToken, setToken } from '../lib/api';
import { useI18n } from '../lib/i18n';

type AuthMode = 'login' | 'register';
type AuthForm = {
  name: string;
  username: string;
  email: string;
  password: string;
  passwordConfirm: string;
  plan: string;
  social: string;
};

type FieldErrors = Partial<Record<keyof AuthForm | 'social', string>>;

const initialForm: AuthForm = {
  name: '',
  username: '',
  email: '',
  password: '',
  passwordConfirm: '',
  plan: 'free',
  social: '',
};

function isValidEmail(value: string) {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value);
}

function isValidUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

function hasStrongPassword(value: string) {
  return /[A-Za-zА-Яа-я]/.test(value) && /\d/.test(value);
}

function normalizeField(field: string): keyof FieldErrors {
  if (field === 'password_confirm') return 'passwordConfirm';
  if (field === 'social_links') return 'social';
  return field as keyof FieldErrors;
}

export default function AuthPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useI18n();
  const [mode, setMode] = useState<AuthMode>('register');
  const [form, setForm] = useState<AuthForm>(initialForm);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  useEffect(() => {
    const reason = searchParams.get('reason') || localStorage.getItem('ghostwriter_auth_notice');
    if (reason) {
      clearToken();
      localStorage.removeItem('ghostwriter_auth_notice');
      setError(t(`auth.errors.${reason}`));
    }
  }, [searchParams, t]);

  function update(field: keyof AuthForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
  }

  function validate(): FieldErrors {
    const next: FieldErrors = {};
    const email = form.email.trim();
    const password = form.password;

    if (mode === 'register') {
      if (!form.name.trim()) next.name = t('auth.errors.NAME_REQUIRED');
      if (!form.username.trim()) next.username = t('auth.errors.USERNAME_REQUIRED');
      if (!email) next.email = t('auth.errors.EMAIL_REQUIRED');
      else if (!isValidEmail(email)) next.email = t('auth.errors.INVALID_EMAIL');
      if (!password) next.password = t('auth.errors.PASSWORD_REQUIRED');
      else if (password.length < 8) next.password = t('auth.errors.PASSWORD_TOO_SHORT');
      else if (!hasStrongPassword(password)) next.password = t('auth.errors.PASSWORD_TOO_WEAK');
      if (form.passwordConfirm && password !== form.passwordConfirm) next.passwordConfirm = t('auth.errors.PASSWORD_CONFIRM_MISMATCH');
      const socialLinks = form.social.split(',').map((item) => item.trim()).filter(Boolean);
      if (socialLinks.some((link) => !isValidUrl(link))) next.social = t('auth.errors.INVALID_SOCIAL_LINKS');
    } else {
      if (!email) next.email = t('auth.errors.LOGIN_REQUIRED');
      if (!password) next.password = t('auth.errors.PASSWORD_REQUIRED');
    }
    return next;
  }

  function showApiError(err: unknown) {
    if (err instanceof ApiError) {
      const translated = err.code ? t(`auth.errors.${err.code}`) : err.message;
      setError(translated || err.message);
      const next: FieldErrors = {};
      if (err.fields) {
        Object.entries(err.fields).forEach(([field, message]) => {
          next[normalizeField(field)] = message;
        });
      }
      if (err.field) {
        next[normalizeField(err.field)] = translated || err.message;
      }
      setFieldErrors(next);
      return;
    }
    setError(t('auth.errors.SERVER_ERROR'));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    const nextErrors = validate();
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      setError(t('auth.errors.VALIDATION_ERROR'));
      return;
    }
    try {
      const payload =
        mode === 'register'
          ? {
              name: form.name.trim(),
              username: form.username.trim(),
              email: form.email.trim(),
              password: form.password,
              password_confirm: form.passwordConfirm || undefined,
              plan: form.plan,
              social_links: form.social.split(',').map((item) => item.trim()).filter(Boolean),
            }
          : { email: form.email.trim(), password: form.password };
      const response = await api<{ access_token: string }>(`/api/auth/${mode}`, { method: 'POST', body: JSON.stringify(payload) });
      setToken(response.access_token);
      navigate(mode === 'register' ? '/onboarding' : '/dashboard');
    } catch (err) {
      showApiError(err);
    }
  }

  function fieldError(field: keyof FieldErrors) {
    return fieldErrors[field] ? <div className="mt-1 text-xs font-medium text-coral">{fieldErrors[field]}</div> : null;
  }

  return (
    <div className="auth-page">
      <header className="auth-header">
        <div className="auth-brand">GhostWriter AI</div>
        <LanguageSwitcher />
      </header>

      <main className="auth-shell">
        <section className="auth-intro" aria-hidden="true">
          <div className="auth-intro__badge">
            <Sparkles size={16} />
            <span>AI content workspace</span>
          </div>
          <h2>Profile → Trends → Posts</h2>
          <p>{t('landing.heroSubtitle')}</p>
          <div className="auth-preview-card">
            <div><CheckCircle2 size={16} /> {t('landing.feature1.title')}</div>
            <div><CheckCircle2 size={16} /> {t('landing.feature2.title')}</div>
            <div><CheckCircle2 size={16} /> {t('landing.feature4.title')}</div>
          </div>
        </section>

        <form onSubmit={submit} className="auth-card">
          <div className="auth-card__head">
            <h1>{t('auth.title')}</h1>
            <p>{t('auth.subtitle')}</p>
          </div>

          <div className="auth-tabs">
            <button type="button" className={mode === 'register' ? 'is-active' : ''} onClick={() => setMode('register')}>
              {t('common.register')}
            </button>
            <button type="button" className={mode === 'login' ? 'is-active' : ''} onClick={() => setMode('login')}>
              {t('common.login')}
            </button>
          </div>

          <div className="auth-fields">
            {mode === 'register' ? (
              <>
                <div>
                  <input className="field auth-field" placeholder={t('auth.name')} value={form.name} onChange={(e) => update('name', e.target.value)} />
                  {fieldError('name')}
                </div>
                <div>
                  <input className="field auth-field" placeholder={t('auth.username')} value={form.username} onChange={(e) => update('username', e.target.value)} />
                  {fieldError('username')}
                </div>
                <select className="field auth-field" value={form.plan} onChange={(e) => update('plan', e.target.value)}>
                  <option value="free">{t('auth.free')}</option>
                  <option value="pro">{t('auth.pro')}</option>
                  <option value="team">{t('auth.team')}</option>
                </select>
                <div>
                  <input className="field auth-field" placeholder={t('auth.socialLinks')} value={form.social} onChange={(e) => update('social', e.target.value)} />
                  {fieldError('social')}
                </div>
              </>
            ) : null}

            <div>
              <input
                className="field auth-field"
                placeholder={mode === 'login' ? t('auth.emailOrUsername') : t('auth.email')}
                type={mode === 'login' ? 'text' : 'email'}
                value={form.email}
                onChange={(e) => update('email', e.target.value)}
              />
              {fieldError('email')}
            </div>
            <div>
              <input className="field auth-field" placeholder={t('auth.password')} type="password" value={form.password} onChange={(e) => update('password', e.target.value)} />
              {fieldError('password')}
            </div>
            {mode === 'register' ? (
              <div>
                <input
                  className="field auth-field"
                  placeholder={t('auth.passwordConfirm')}
                  type="password"
                  value={form.passwordConfirm}
                  onChange={(e) => update('passwordConfirm', e.target.value)}
                />
                {fieldError('passwordConfirm')}
              </div>
            ) : null}
          </div>

          <div className="auth-helper">{t('auth.passwordHint')}</div>
          {error ? (
            <div className="auth-error">
              <div>{t('auth.errorTitle')}</div>
              <p>{error}</p>
            </div>
          ) : null}
          <button className="primary-button auth-submit" type="submit">{t('common.continue')}</button>
        </form>
      </main>
    </div>
  );
}
