import { ArrowRight, LogIn, PanelsTopLeft, MessageSquareText, BarChart3 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { LanguageSwitcher } from '../components/LanguageSwitcher';
import { getToken } from '../lib/api';
import { useI18n } from '../lib/i18n';

export default function LandingPage() {
  const { t } = useI18n();
  return (
    <div className="aurora-app min-h-screen text-ink">
      <header className="relative z-10 flex items-center justify-between border-b border-black/10 px-6 py-5 lg:px-12">
        <div className="aurora-brand text-lg font-bold">{t('app.name')}</div>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <Link to={getToken() ? '/dashboard' : '/auth'} className="secondary-button">
            <LogIn size={16} /> {getToken() ? t('nav.menu') : t('common.login')}
          </Link>
        </div>
      </header>
      <main className="aurora-hero grid min-h-[calc(100vh-82px)] items-center gap-10 px-6 py-14 lg:grid-cols-[1.05fr_0.95fr] lg:px-12">
        <section className="max-w-3xl">
          <h1 className="text-5xl font-bold tracking-normal sm:text-6xl lg:text-7xl">{t('landing.title')}</h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-black/70">{t('landing.text')}</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link to={getToken() ? '/dashboard' : '/auth'} className="primary-button">
              {t('common.start')} <ArrowRight size={18} />
            </Link>
            <Link to="/auth" className="secondary-button">{t('common.createAccount')}</Link>
          </div>
        </section>
        <section className="grid gap-4">
          {[
            { icon: PanelsTopLeft, label: t('landing.card1'), color: 'bg-teal/10 text-teal' },
            { icon: BarChart3, label: t('landing.card2'), color: 'bg-grape/10 text-grape' },
            { icon: MessageSquareText, label: t('landing.card3'), color: 'bg-amber/20 text-ink' },
          ].map(({ icon: Icon, label, color }) => (
            <div key={label} className="panel flex items-center gap-4 p-5">
              <div className={`flex h-14 w-14 items-center justify-center ${color}`} style={{ borderRadius: 8 }}>
                <Icon size={26} />
              </div>
              <div className="text-xl font-bold">{label}</div>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
