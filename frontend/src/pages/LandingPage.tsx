import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  CalendarCheck,
  Camera,
  CheckCircle2,
  Flame,
  Globe2,
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

const previewCopy = {
  ru: {
    metrics: ['Заполненность профиля', 'Активные тренды', 'Соцаккаунты', 'Главный тренд'],
    profileTitle: 'Профиль готов к генерации',
    profileSummary: 'Python-разработчик · IT · найти клиентов',
    profileMeta: 'Аудитория: IT-компании и технические руководители',
    styleTitle: 'Посты в индивидуальном стиле',
    styleFlow: 'Hook -> insight -> case -> CTA',
    socialTitle: 'Платформы и публикации',
    sourceTitle: 'Карта источников',
    chartTitle: 'Публикации и аналитика',
    published: 'Опубликовано',
    scheduled: 'Запланировано',
    cancelled: 'Отменено',
  },
  en: {
    metrics: ['Profile completeness', 'Active trends', 'Connected platforms', 'Main trend score'],
    profileTitle: 'Profile ready for content',
    profileSummary: 'Python developer · IT · client acquisition',
    profileMeta: 'Audience: IT companies and technical leaders',
    styleTitle: 'Posts in personal style',
    styleFlow: 'Hook -> insight -> case -> CTA',
    socialTitle: 'Platforms and posts',
    sourceTitle: 'Source map',
    chartTitle: 'Publishing analytics',
    published: 'Published',
    scheduled: 'Scheduled',
    cancelled: 'Cancelled',
  },
  kz: {
    metrics: ['Профиль толықтығы', 'Белсенді трендтер', 'Қосылған платформалар', 'Негізгі тренд ұпайы'],
    profileTitle: 'Профиль контентке дайын',
    profileSummary: 'Python әзірлеуші · IT · клиент табу',
    profileMeta: 'Аудитория: IT компаниялар және техникалық жетекшілер',
    styleTitle: 'Жеке стильдегі посттар',
    styleFlow: 'Hook -> insight -> case -> CTA',
    socialTitle: 'Платформалар мен жарияланымдар',
    sourceTitle: 'Дереккөз картасы',
    chartTitle: 'Жариялау аналитикасы',
    published: 'Жарияланды',
    scheduled: 'Жоспарланды',
    cancelled: 'Болдырылды',
  },
};

export default function LandingPage() {
  const { t, lang } = useI18n();
  const authenticated = Boolean(getToken());
  const startRoute = authenticated ? '/dashboard' : '/auth';
  const secondaryRoute = authenticated ? '/chat' : '/auth';
  const preview = previewCopy[lang] || previewCopy.ru;

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

          <div className="landing-analytics-preview" aria-label="GhostWriter AI analytics preview">
            <div className="landing-dashboard__top landing-analytics-preview__top">
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

            <div className="landing-metric-strip">
              <article className="landing-metric-card landing-metric-card--cyan">
                <UserRound size={18} />
                <span>{preview.metrics[0]}</span>
                <strong>100%</strong>
              </article>
              <article className="landing-metric-card landing-metric-card--orange">
                <TrendingUp size={18} />
                <span>{preview.metrics[1]}</span>
                <strong>64</strong>
              </article>
              <article className="landing-metric-card landing-metric-card--teal">
                <Globe2 size={18} />
                <span>{preview.metrics[2]}</span>
                <strong>8</strong>
              </article>
              <article className="landing-metric-card landing-metric-card--violet">
                <Flame size={18} />
                <span>{preview.metrics[3]}</span>
                <strong>93</strong>
              </article>
            </div>

            <div className="landing-analytics-grid">
              <article className="landing-analytics-card landing-analytics-card--profile">
                <div className="landing-analytics-card__head">
                  <UserRound size={22} />
                  <span>{preview.profileTitle}</span>
                  <strong>100%</strong>
                </div>
                <div className="landing-progress" aria-hidden="true">
                  <i style={{ width: '100%' }} />
                </div>
                <h3>{preview.profileSummary}</h3>
                <p>{preview.profileMeta}</p>
                <div className="landing-chip-row landing-chip-row--compact">
                  <span>Telegram</span>
                  <span>LinkedIn</span>
                  <span>Expert tone</span>
                  <span>Audience</span>
                </div>
              </article>

              <article className="landing-analytics-card landing-analytics-card--style">
                <div className="landing-analytics-card__head">
                  <PenTool size={22} />
                  <span>{preview.styleTitle}</span>
                  <p className="landing-style-flow">{preview.styleFlow}</p>
                </div>
                <p>Hook → insight → example → CTA</p>
                <div className="landing-preview-lines landing-preview-lines--short">
                  <i />
                  <i />
                  <i />
                </div>
              </article>

              <article className="landing-analytics-card landing-analytics-card--social">
                <div className="landing-analytics-card__head">
                  <Globe2 size={22} />
                  <span>{preview.socialTitle}</span>
                </div>
                <div className="landing-platform-rows">
                  <div className="landing-platform-row">
                    <span>Telegram</span>
                    <b>8</b>
                  </div>
                  <div className="landing-platform-row">
                    <span>{preview.published}</span>
                    <b>4</b>
                  </div>
                  <div className="landing-platform-row">
                    <span>{preview.scheduled}</span>
                    <b>3</b>
                  </div>
                  <div className="landing-platform-row">
                    <span>{preview.cancelled}</span>
                    <b>1</b>
                  </div>
                </div>
              </article>

              <article className="landing-analytics-card landing-analytics-card--chart">
                <div className="landing-analytics-card__head">
                  <Activity size={22} />
                  <span>{preview.chartTitle}</span>
                  <small>{preview.sourceTitle}</small>
                </div>
                <div className="landing-chart-bars" aria-hidden="true">
                  {[44, 62, 51, 76, 68, 86, 58].map((height, index) => (
                    <span key={index} style={{ height: `${height}%` }} />
                  ))}
                </div>
                <div className="landing-source-summary">
                  <span>rss 459</span>
                  <span>demo 14</span>
                  <span>profile_context 2</span>
                  <span>Trends</span>
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
