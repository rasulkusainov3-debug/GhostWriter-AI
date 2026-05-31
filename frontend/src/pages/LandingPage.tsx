import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  CalendarCheck,
  Camera,
  CheckCircle2,
  Layers3,
  LogIn,
  MessageSquareText,
  PenTool,
  Search,
  Sparkles,
  TrendingUp,
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
    <div className="landing-page">
      <header className="landing-header">
        <div className="landing-header__inner">
          <Link to="/" className="landing-brand">{t('app.name')}</Link>
          <nav className="landing-nav" aria-label="Landing navigation">
            <a href="#about">{t('landing.aboutTitle')}</a>
            <a href="#features">{t('landing.featuresTitle')}</a>
            <a href="#workflow">{t('landing.stepsTitle')}</a>
            <a href="#agents">{t('landing.agentsTitle')}</a>
          </nav>
          <div className="landing-nav-actions">
            <LanguageSwitcher />
            <Link to={startRoute} className="secondary-button landing-login">
              <LogIn size={16} /> {authenticated ? t('nav.menu') : t('common.login')}
            </Link>
          </div>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero reveal-section">
          <div className="landing-hero__halo landing-hero__halo--orange" />
          <div className="landing-hero__halo landing-hero__halo--cyan" />
          <div className="landing-hero__intro">
            <div className="landing-pill">
              <Sparkles size={15} />
              <span>AI content workspace</span>
            </div>
            <h1>{t('landing.heroHeadline')}</h1>
            <p>{t('landing.heroSubtitle')}</p>
            <div className="landing-cta-row landing-cta-row--center">
              <Link to={startRoute} className="primary-button landing-primary">
                {t('common.start')} <ArrowRight size={18} />
              </Link>
              <Link to={secondaryRoute} className="secondary-button">
                {authenticated ? t('landing.ctaChat') : t('common.createAccount')}
              </Link>
            </div>
          </div>

          <div className="landing-dashboard" aria-label="GhostWriter AI product preview">
            <div className="landing-dashboard__top">
              <div className="landing-dashboard__brand">
                <span className="landing-logo-mark"><Sparkles size={18} /></span>
                <strong>{t('app.name')}</strong>
              </div>
              <div className="landing-dashboard__tabs">
                <span>Profile</span>
                <span>Trends</span>
                <span>Posts</span>
                <span>Visuals</span>
                <span>Metrics</span>
              </div>
            </div>

            <div className="landing-dashboard__grid">
              <article className="landing-preview-card landing-preview-card--profile">
                <div className="landing-preview-card__head">
                  <UserRound size={22} />
                  <span>{t('landing.feature1.title')}</span>
                </div>
                <div className="landing-preview-lines">
                  <i className="w-5/6" />
                  <i className="w-2/3" />
                  <i className="w-4/6" />
                </div>
                <div className="landing-chip-row">
                  <span>LinkedIn</span>
                  <span>Telegram</span>
                  <span>Expert tone</span>
                </div>
              </article>

              <article className="landing-preview-card landing-preview-card--accent">
                <TrendingUp size={24} />
                <span>{t('landing.feature2.title')}</span>
                <strong>8</strong>
                <small>high relevance</small>
              </article>

              <article className="landing-preview-card">
                <div className="landing-preview-card__head">
                  <PenTool size={22} />
                  <span>{t('landing.feature4.title')}</span>
                </div>
                <p>Hook → insight → example → CTA</p>
                <div className="landing-post-skeleton">
                  <i />
                  <i />
                  <i />
                </div>
              </article>

              <article className="landing-preview-card landing-preview-card--chart">
                <div className="landing-preview-card__head">
                  <Activity size={22} />
                  <span>{t('landing.feature6.title')}</span>
                </div>
                <div className="landing-bars">
                  {[42, 64, 52, 78, 68, 88, 58].map((height, index) => (
                    <span key={index} style={{ height: `${height}%` }} />
                  ))}
                </div>
              </article>
            </div>
          </div>
        </section>

        <section className="landing-trust reveal-section">
          <span>Profile context</span>
          <span>Trend relevance</span>
          <span>Platform style</span>
          <span>Visual workflow</span>
          <span>Manual metrics</span>
        </section>

        <section id="about" className="landing-section landing-about reveal-section">
          <div className="landing-section__head landing-section__head--center">
            <h2>{t('landing.aboutTitle')}</h2>
            <p>{t('landing.aboutText')}</p>
          </div>
        </section>

        <section id="features" className="landing-section reveal-section">
          <div className="landing-section__head landing-section__head--center">
            <h2>{t('landing.featuresTitle')}</h2>
            <p>{t('landing.featuresText')}</p>
          </div>
          <div className="landing-feature-grid">
            {features.map(({ Icon, title, text }) => (
              <article key={title} className="landing-feature-card">
                <div className="landing-icon"><Icon size={24} /></div>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="workflow" className="landing-section reveal-section">
          <div className="landing-section__head landing-section__head--center">
            <h2>{t('landing.stepsTitle')}</h2>
            <p>{t('landing.stepsText')}</p>
          </div>
          <div className="landing-steps">
            {steps.map(({ Icon, title, text }, index) => (
              <article key={title} className="landing-step-card">
                <div className="landing-step-card__number">{index + 1}</div>
                <div className="landing-icon"><Icon size={24} /></div>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="agents" className="landing-section landing-agents reveal-section">
          <div className="landing-section__head">
            <h2>{t('landing.agentsTitle')}</h2>
            <p>{t('landing.agentsText')}</p>
          </div>
          <div className="landing-agent-grid">
            <article className="landing-agent-card">
              <div className="landing-icon"><Bot size={24} /></div>
              <h3>{t('landing.analyzerTitle')}</h3>
              <p>{t('landing.analyzerText')}</p>
            </article>
            <article className="landing-agent-card">
              <div className="landing-icon"><Sparkles size={24} /></div>
              <h3>{t('landing.creatorTitle')}</h3>
              <p>{t('landing.creatorText')}</p>
            </article>
            <article className="landing-agent-card">
              <div className="landing-icon"><BarChart3 size={24} /></div>
              <h3>Publisher / Analytics</h3>
              <p>{t('landing.feature6.text')}</p>
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
