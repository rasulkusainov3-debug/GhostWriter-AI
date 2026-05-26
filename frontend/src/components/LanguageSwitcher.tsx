import { Languages } from 'lucide-react';
import { useI18n } from '../lib/i18n';

export function LanguageSwitcher() {
  const { lang, setLang } = useI18n();
  return (
    <div className="inline-flex items-center gap-1 border border-black/10 bg-white p-1 shadow-soft" style={{ borderRadius: 8 }}>
      <Languages size={16} className="mx-2 text-black/50" />
      {(['ru', 'en'] as const).map((code) => (
        <button
          key={code}
          className={`px-2 py-1 text-xs font-bold uppercase ${lang === code ? 'bg-ink text-white' : 'text-black/60 hover:text-ink'}`}
          style={{ borderRadius: 6 }}
          onClick={() => setLang(code)}
          type="button"
        >
          {code}
        </button>
      ))}
    </div>
  );
}
