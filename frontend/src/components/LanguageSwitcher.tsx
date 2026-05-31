import { Languages } from 'lucide-react';
import { useI18n } from '../lib/i18n';

export function LanguageSwitcher() {
  const { lang, setLang } = useI18n();
  const languages = [
    { code: 'ru', short: 'RU', label: 'Русский' },
    { code: 'en', short: 'EN', label: 'English' },
    { code: 'kz', short: 'KZ', label: 'Қазақша' },
  ] as const;

  return (
    <div className="language-switcher">
      <Languages size={15} className="language-switcher__icon" />
      {languages.map(({ code, short, label }) => (
        <button
          key={code}
          aria-label={label}
          className={`language-switcher__button ${lang === code ? 'is-active' : ''}`}
          onClick={() => setLang(code)}
          title={label}
          type="button"
        >
          {short}
        </button>
      ))}
    </div>
  );
}
