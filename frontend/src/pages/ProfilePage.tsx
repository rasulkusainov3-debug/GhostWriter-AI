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
    ['audience', t('profile.audience')],
    ['tone', t('profile.tone')],
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
    <div className="profile-editor">
      <header className="profile-editor__header">
        <div>
          <h1>{t('profile.title')}</h1>
          <p>{t('profile.desc')}</p>
        </div>
        <button className="primary-button profile-editor__save" onClick={save} disabled={saving}>
          <Save size={17} />
          {t('common.save')}
        </button>
      </header>
      <ErrorNotice message={error} />
      {saved ? <div className="profile-save-notice">{t('common.saved')}</div> : null}

      <div className="profile-layout">
        <section className="profile-card panel">
          <div className="profile-card__header">
            <div className="profile-avatar">{(profile.name || 'G').slice(0, 1)}</div>
            <div>
              <h2>{t('profile.title')}</h2>
              <p>{profile.profession || t('profile.professionUnset')}</p>
            </div>
          </div>

          <div className="profile-form-grid">
            {fields.map(([field, label]) => (
              <label key={field} className={`profile-field ${field === 'audience' || field === 'avoid' ? 'profile-field--wide' : ''}`}>
                <span>{label}</span>
                {field === 'audience' || field === 'avoid' ? (
                  <textarea
                    className="field profile-input profile-textarea"
                    value={(profile[field] as string) || ''}
                    onChange={(e) => setProfile({ ...profile, [field]: e.target.value })}
                  />
                ) : (
                  <input
                    className="field profile-input"
                    value={(profile[field] as string) || ''}
                    onChange={(e) => setProfile({ ...profile, [field]: e.target.value })}
                  />
                )}
              </label>
            ))}
            <label className="profile-field profile-field--wide">
              <span>{t('profile.values')}</span>
              <input
                className="field profile-input"
                value={(profile.user_values || []).join(', ')}
                onChange={(e) => setProfile({ ...profile, user_values: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })}
              />
              <small>{t('profile.styleTagsHelp')}</small>
            </label>
            <label className="profile-field profile-field--wide">
              <span>{t('profile.platforms')}</span>
              <input
                className="field profile-input"
                value={(profile.platforms || []).join(', ')}
                onChange={(e) => setProfile({ ...profile, platforms: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })}
              />
              <small>{t('profile.styleTagsHelp')}</small>
            </label>
          </div>
        </section>

        <section className="profile-card profile-style-card panel">
          <div className="profile-card__topline">
            <div>
              <h2>
                <Sparkles size={18} className="text-gold" />
                {t('profile.styleTitle')}
              </h2>
              <p>{t('profile.styleHelp')}</p>
            </div>
            <span className="profile-style-count">
              {t('profile.styleExamples')}: {styleExamplesCount}
            </span>
          </div>

          <div className="profile-style-grid">
            <label className="profile-field">
              <span>{t('profile.styleVoice')}</span>
              <input
                className="field profile-input"
                placeholder={t('profile.styleVoicePlaceholder')}
                value={personality.voice || ''}
                onChange={(e) => updatePersonality({ voice: e.target.value })}
              />
            </label>
            <label className="profile-field profile-field--wide">
              <span>{t('profile.styleWriting')}</span>
              <textarea
                className="field profile-input profile-textarea profile-textarea--large"
                placeholder={t('profile.styleWritingPlaceholder')}
                value={personality.writing_style || ''}
                onChange={(e) => updatePersonality({ writing_style: e.target.value })}
              />
            </label>
            <label className="profile-field">
              <span>{t('profile.styleStructure')}</span>
              <input
                className="field profile-input"
                value={(personality.preferred_structure || []).join(', ')}
                onChange={(e) => updatePersonality({ preferred_structure: splitTags(e.target.value) })}
              />
              <small>{t('profile.styleTagsHelp')}</small>
            </label>
            <label className="profile-field">
              <span>{t('profile.styleVocabulary')}</span>
              <input
                className="field profile-input"
                placeholder={t('profile.styleVocabularyPlaceholder')}
                value={(personality.vocabulary_preferences || []).join(', ')}
                onChange={(e) => updatePersonality({ vocabulary_preferences: splitTags(e.target.value) })}
              />
              <small>{t('profile.styleTagsHelp')}</small>
            </label>
            <label className="profile-field profile-field--wide">
              <span>{t('profile.styleAvoidPhrases')}</span>
              <input
                className="field profile-input"
                placeholder={t('profile.styleAvoidPlaceholder')}
                value={(personality.avoid_phrases || []).join(', ')}
                onChange={(e) => updatePersonality({ avoid_phrases: splitTags(e.target.value) })}
              />
              <small>{t('profile.styleTagsHelp')}</small>
            </label>
          </div>
        </section>
      </div>
    </div>
  );
}
