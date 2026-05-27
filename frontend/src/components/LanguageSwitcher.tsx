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
    <div className="language-switcher inline-flex items-center gap-1 border border-black/10 bg-white p-1 shadow-soft" style={{ borderRadius: 8 }}>
      <Languages size={16} className="mx-2 text-black/50" />
      {languages.map(({ code, short, label }) => (
        <button
          key={code}
          aria-label={label}
          className={`language-switcher__button px-2 py-1 text-xs font-bold uppercase ${lang === code ? 'bg-ink text-white' : 'text-black/60 hover:text-ink'}`}
          style={{ borderRadius: 6 }}
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
