import { useEffect, useRef, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { BarChart3, FileClock, FileText, LayoutDashboard, LogOut, Menu, MessageSquareText, PenLine, UserRound, UsersRound } from 'lucide-react';
import { clearToken } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { LanguageSwitcher } from './LanguageSwitcher';

const links = [
  { to: '/dashboard', labelKey: 'dashboard.title', icon: LayoutDashboard },
  { to: '/chat', labelKey: 'nav.chat', icon: MessageSquareText },
  { to: '/profile', labelKey: 'nav.profile', icon: UserRound },
  { to: '/history', labelKey: 'nav.history', icon: FileClock },
  { to: '/content-plans', labelKey: 'nav.plans', icon: PenLine },
  { to: '/generated-posts', labelKey: 'nav.posts', icon: FileText },
  { to: '/analytics/profile', labelKey: 'nav.profileAnalytics', icon: BarChart3 },
  { to: '/analytics/social', labelKey: 'nav.socialAnalytics', icon: UsersRound },
  { to: '/content-plans', labelKey: 'planAnalytics.title', icon: BarChart3 },
];

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useI18n();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false);
    }
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen]);

  function isActive(to: string, labelKey: string) {
    if (labelKey === 'planAnalytics.title') return location.pathname.includes('/analytics') && location.pathname.startsWith('/content-plans/');
    if (to === '/dashboard') return location.pathname === '/dashboard';
    if (to === '/content-plans') return location.pathname === '/content-plans' || (location.pathname.startsWith('/content-plans/') && !location.pathname.includes('/analytics'));
    return location.pathname === to;
  }

  function logout() {
    clearToken();
    setMenuOpen(false);
    navigate('/');
  }

  return (
    <div className="aurora-app aurora-shell text-ink">
      <main>
        <div className="aurora-topbar sticky top-0 z-30 px-4 py-3">
          <div className="app-shell-header">
            <Link className="aurora-brand app-brand-link" to="/dashboard">{t('app.name')}</Link>
            <div className="app-shell-actions">
              <div className="app-menu-wrap" ref={menuRef}>
                <button
                  aria-controls="app-main-menu"
                  aria-expanded={menuOpen}
                  className="secondary-button px-3 py-2 text-xs"
                  onClick={() => setMenuOpen((value) => !value)}
                  type="button"
                >
                  <Menu size={15} /> {t('nav.menu')}
                </button>
                {menuOpen ? (
                  <nav className="app-menu-dropdown panel" id="app-main-menu">
                    <div className="app-menu-list">
                      {links.map(({ to, labelKey, icon: Icon }) => {
                        const active = isActive(to, labelKey);
                        return (
                          <Link
                            key={`${to}-${labelKey}`}
                            className={`app-menu-item ${active ? 'is-active' : ''}`}
                            onClick={() => setMenuOpen(false)}
                            to={to}
                          >
                            <span className="app-menu-item__icon"><Icon size={17} /></span>
                            <span className="app-menu-item__text">{t(labelKey)}</span>
                          </Link>
                        );
                      })}
                    </div>
                    <button className="app-menu-logout" onClick={logout} type="button">
                      <LogOut size={16} /> {t('common.logout')}
                    </button>
                  </nav>
                ) : null}
              </div>
              <LanguageSwitcher />
            </div>
          </div>
        </div>
        <div className={`aurora-content mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 ${location.pathname.startsWith('/chat') ? 'aurora-content--chat' : ''}`}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
