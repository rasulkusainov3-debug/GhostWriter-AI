import {
  ArrowRight,
  BarChart3,
  Bot,
  CalendarCheck,
  Camera,
  CheckCircle2,
  Layers3,
  LogIn,
  MessageSquareText,
  Search,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { LanguageSwitcher } from '../components/LanguageSwitcher';
import { getToken } from '../lib/api';
import { useI18n } from '../lib/i18n';

const featureIcons = [UserRound, Search, Layers3, MessageSquareText, Camera, BarChart3];
const stepIcons = [UserRound, Search, Sparkles, CalendarCheck];

export default function LandingPage() {
  const { t } = useI18n();
  const authenticated = Boolean(getToken());
  const startRoute = authenticated ? '/dashboard' : '/auth';
  const secondaryRoute = authenticated ? '/chat' : '/auth';

  const features = Array.from({ length: 6 }, (_, index) => {
    const Icon = featureIcons[index];
    return {
      Icon,
      title: t(`landing.feature${index + 1}.title`),
      text: t(`landing.feature${index + 1}.text`),
    };
  });

  const steps = Array.from({ length: 4 }, (_, index) => {
    const Icon = stepIcons[index];
    return {
      Icon,
      title: t(`landing.step${index + 1}.title`),
      text: t(`landing.step${index + 1}.text`),
    };
  });

  return (
    <div className="aurora-app landing-page text-ink">
      <header className="landing-header">
        <Link to="/" className="aurora-brand landing-brand">{t('app.name')}</Link>
        <div className="landing-nav-actions">
          <LanguageSwitcher />
          <Link to={startRoute} className="secondary-button">
            <LogIn size={16} /> {authenticated ? t('nav.menu') : t('common.login')}
          </Link>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero reveal-section">
          <div className="landing-glow landing-glow--one" />
          <div className="landing-glow landing-glow--two" />
          <div className="landing-hero__content">
            <div className="landing-hero__copy">
              <h1>{t('landing.heroHeadline')}</h1>
              <p>{t('landing.heroSubtitle')}</p>
              <div className="landing-cta-row">
                <Link to={startRoute} className="primary-button landing-primary">
                  {t('common.start')} <ArrowRight size={18} />
                </Link>
                <Link to={secondaryRoute} className="secondary-button">
                  {authenticated ? t('landing.ctaChat') : t('common.createAccount')}
                </Link>
              </div>
            </div>
            <div className="landing-hero-card">
              <div className="landing-hero-card__top">
                <span>{t('landing.heroCardTitle')}</span>
                <Sparkles size={18} />
              </div>
              <div className="landing-signal-list">
                <div><CheckCircle2 size={16} /> {t('landing.signal1')}</div>
                <div><CheckCircle2 size={16} /> {t('landing.signal2')}</div>
                <div><CheckCircle2 size={16} /> {t('landing.signal3')}</div>
              </div>
              <div className="landing-mini-preview">
                <div className="landing-mini-preview__line w-5/6" />
                <div className="landing-mini-preview__line w-2/3" />
                <div className="landing-mini-preview__tags">
                  <span>LinkedIn</span>
                  <span>Telegram</span>
                  <span>AI trends</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="landing-section landing-about reveal-section">
          <div className="landing-section__head">
            <h2>{t('landing.aboutTitle')}</h2>
            <p>{t('landing.aboutText')}</p>
          </div>
        </section>

        <section className="landing-section reveal-section">
          <div className="landing-section__head">
            <h2>{t('landing.featuresTitle')}</h2>
            <p>{t('landing.featuresText')}</p>
          </div>
          <div className="landing-feature-grid">
            {features.map(({ Icon, title, text }) => (
              <article key={title} className="landing-feature-card">
                <div className="landing-icon"><Icon size={22} /></div>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section reveal-section">
          <div className="landing-section__head landing-section__head--split">
            <div>
              <h2>{t('landing.stepsTitle')}</h2>
              <p>{t('landing.stepsText')}</p>
            </div>
            <Link to={startRoute} className="secondary-button">{t('common.start')}</Link>
          </div>
          <div className="landing-steps">
            {steps.map(({ Icon, title, text }, index) => (
              <article key={title} className="landing-step-card">
                <div className="landing-step-card__number">{index + 1}</div>
                <Icon size={22} />
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section landing-agents reveal-section">
          <div className="landing-section__head">
            <h2>{t('landing.agentsTitle')}</h2>
            <p>{t('landing.agentsText')}</p>
          </div>
          <div className="landing-agent-grid">
            <article className="landing-agent-card">
              <Bot size={24} />
              <h3>{t('landing.analyzerTitle')}</h3>
              <p>{t('landing.analyzerText')}</p>
            </article>
            <article className="landing-agent-card">
              <Sparkles size={24} />
              <h3>{t('landing.creatorTitle')}</h3>
              <p>{t('landing.creatorText')}</p>
            </article>
          </div>
        </section>

        <section className="landing-final-cta reveal-section">
          <h2>{t('landing.finalCtaTitle')}</h2>
          <p>{t('landing.finalCtaText')}</p>
          <div className="landing-cta-row landing-cta-row--center">
            <Link to={startRoute} className="primary-button landing-primary">
              {t('common.start')} <ArrowRight size={18} />
            </Link>
            <Link to={secondaryRoute} className="secondary-button">
              {authenticated ? t('landing.ctaChat') : t('common.createAccount')}
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
