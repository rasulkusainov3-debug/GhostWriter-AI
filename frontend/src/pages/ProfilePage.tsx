import { Save, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { api, errorMessage } from '../lib/api';
import { useI18n } from '../lib/i18n';
import type { PersonalityStyle, Profile } from '../types';

const defaultStructure = ['hook', 'insight', 'example', 'CTA'];

function splitTags(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function personalityFromProfile(profile: Profile): PersonalityStyle {
  const raw = profile.raw_answers || {};
  const personality = raw.personality && typeof raw.personality === 'object' ? raw.personality : {};
  return {
    voice: personality.voice || '',
    writing_style: personality.writing_style || '',
    preferred_structure: personality.preferred_structure?.length ? personality.preferred_structure : defaultStructure,
    vocabulary_preferences: personality.vocabulary_preferences || [],
    avoid_phrases: personality.avoid_phrases || [],
    example_post_ids: personality.example_post_ids || [],
  };
}

export default function ProfilePage() {
  const { t } = useI18n();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const profileData = await api<Profile>('/api/profiles/me');
      setProfile(profileData);
    } catch (err) {
      setError(errorMessage(err, t('common.loadError')));
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save() {
    if (!profile) return;
    setError('');
    setSaved(false);
    setSaving(true);
    try {
      const updated = await api<Profile>('/api/profiles/me', { method: 'PATCH', body: JSON.stringify(profile) });
      setProfile(updated);
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err, t('common.error')));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <PageHeader title={t('profile.title')} description={t('common.loading')} />;
  if (!profile) {
    return (
      <>
        <PageHeader title={t('profile.title')} description={t('profile.desc')} />
        <ErrorNotice message={error || t('chat.noProfile')} onRetry={load} />
        <Link className="primary-button" to="/onboarding">{t('onboarding.title')}</Link>
      </>
    );
  }

  const fields = [
    ['name', t('profile.name')],
    ['niche', t('profile.niche')],
    ['profession', t('profile.profession')],
    ['goal', t('profile.goal')],
    ['tone', t('profile.tone')],
    ['audience', t('profile.audience')],
    ['avoid', t('profile.avoid')],
  ] as const;

  const personality = personalityFromProfile(profile);
  const styleExamplesCount = profile.style_examples_count ?? personality.example_post_ids?.length ?? 0;

  function updatePersonality(patch: Partial<PersonalityStyle>) {
    setProfile((current) => {
      if (!current) return current;
      const currentPersonality = personalityFromProfile(current);
      return {
        ...current,
        raw_answers: {
          ...(current.raw_answers || {}),
          personality: {
            ...currentPersonality,
            ...patch,
          },
        },
      };
    });
    setSaved(false);
  }

  return (
    <>
      <PageHeader title={t('profile.title')} description={t('profile.desc')} action={<button className="primary-button" onClick={save} disabled={saving}><Save size={16} /> {t('common.save')}</button>} />
      <ErrorNotice message={error} />
      {saved ? <div className="mb-4 rounded-md border border-teal/20 bg-teal/10 p-3 text-sm font-semibold text-teal">{t('common.saved')}</div> : null}
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="panel p-5">
          <div className="mx-auto flex h-28 w-28 items-center justify-center rounded-full bg-teal/10 text-4xl font-bold text-teal">
            {(profile.name || 'G').slice(0, 1)}
          </div>
          <div className="mt-5 text-center">
            <div className="text-xl font-bold">{profile.name || t('profile.unnamed')}</div>
            <div className="mt-1 text-sm text-black/50">{profile.profession || t('profile.professionUnset')}</div>
          </div>
        </aside>
        <section className="panel p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            {fields.map(([field, label]) => (
              <label key={field} className="text-sm font-semibold">
                {label}
                <input className="field mt-1" value={(profile[field] as string) || ''} onChange={(e) => setProfile({ ...profile, [field]: e.target.value })} />
              </label>
            ))}
            <label className="text-sm font-semibold">
              {t('profile.values')}
              <input className="field mt-1" value={(profile.user_values || []).join(', ')} onChange={(e) => setProfile({ ...profile, user_values: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })} />
            </label>
            <label className="text-sm font-semibold">
              {t('profile.platforms')}
              <input className="field mt-1" value={(profile.platforms || []).join(', ')} onChange={(e) => setProfile({ ...profile, platforms: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })} />
            </label>
          </div>
        </section>
        <section className="panel p-5 lg:col-span-2">
          <div className="mb-5 flex flex-col gap-3 border-b border-white/10 pb-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-lg font-bold">
                <Sparkles size={18} className="text-gold" />
                {t('profile.styleTitle')}
              </div>
              <p className="mt-1 max-w-2xl text-sm text-black/55">{t('profile.styleHelp')}</p>
            </div>
            <span className="w-fit rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-bold text-black/60">
              {t('profile.styleExamples')}: {styleExamplesCount}
            </span>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <label className="text-sm font-semibold">
              {t('profile.styleVoice')}
              <input
                className="field mt-1"
                placeholder={t('profile.styleVoicePlaceholder')}
                value={personality.voice || ''}
                onChange={(e) => updatePersonality({ voice: e.target.value })}
              />
            </label>
            <label className="text-sm font-semibold">
              {t('profile.styleWriting')}
              <textarea
                className="field mt-1 min-h-24 resize-y"
                placeholder={t('profile.styleWritingPlaceholder')}
                value={personality.writing_style || ''}
                onChange={(e) => updatePersonality({ writing_style: e.target.value })}
              />
            </label>
            <label className="text-sm font-semibold">
              {t('profile.styleStructure')}
              <input
                className="field mt-1"
                value={(personality.preferred_structure || []).join(', ')}
                onChange={(e) => updatePersonality({ preferred_structure: splitTags(e.target.value) })}
              />
              <span className="mt-1 block text-xs text-black/45">{t('profile.styleTagsHelp')}</span>
            </label>
            <label className="text-sm font-semibold">
              {t('profile.styleVocabulary')}
              <input
                className="field mt-1"
                placeholder={t('profile.styleVocabularyPlaceholder')}
                value={(personality.vocabulary_preferences || []).join(', ')}
                onChange={(e) => updatePersonality({ vocabulary_preferences: splitTags(e.target.value) })}
              />
              <span className="mt-1 block text-xs text-black/45">{t('profile.styleTagsHelp')}</span>
            </label>
            <label className="text-sm font-semibold lg:col-span-2">
              {t('profile.styleAvoidPhrases')}
              <input
                className="field mt-1"
                placeholder={t('profile.styleAvoidPlaceholder')}
                value={(personality.avoid_phrases || []).join(', ')}
                onChange={(e) => updatePersonality({ avoid_phrases: splitTags(e.target.value) })}
              />
              <span className="mt-1 block text-xs text-black/45">{t('profile.styleTagsHelp')}</span>
            </label>
          </div>
        </section>
      </div>
    </>
  );
}
