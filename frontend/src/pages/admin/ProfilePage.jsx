import { useEffect, useRef, useState } from 'react';
import { Edit3, Eye, EyeOff, Globe2, LoaderCircle, Save, UserRound } from 'lucide-react';
import { api } from '../../api';
import Toast, { ToastStack } from '../../components/Toast';
import ResumeImport from '../../components/ResumeImport';

const fields = [
  { key: 'full_name', label: 'Full name', type: 'text', placeholder: 'Your full name', group: 'Basics', publicable: true },
  { key: 'headline', label: 'Professional headline', type: 'text', placeholder: 'Full-stack developer | React · Python', group: 'Basics', publicable: true },
  { key: 'objective', label: 'Career objective', type: 'textarea', rows: 3, placeholder: 'A short, factual career objective…', group: 'Basics', publicable: true },
  { key: 'preferred_roles', label: 'Preferred roles', type: 'textarea', rows: 2, placeholder: 'Software Developer, MERN Developer…', group: 'Basics', publicable: true },
  { key: 'location', label: 'Location', type: 'text', placeholder: 'City, State, Country', group: 'Contact & links', publicable: true },
  { key: 'phone', label: 'Phone number', type: 'tel', placeholder: '+91 98765 43210', group: 'Contact & links', publicable: true },
  { key: 'email', label: 'Email address', type: 'email', placeholder: 'you@example.com', group: 'Contact & links', publicable: true },
  { key: 'github_url', label: 'GitHub username', type: 'text', placeholder: 'username', prefix: 'https://github.com/', group: 'Contact & links', publicable: true },
  { key: 'linkedin_url', label: 'LinkedIn username', type: 'text', placeholder: 'username', prefix: 'https://linkedin.com/in/', group: 'Contact & links', publicable: true },
  { key: 'website_url', label: 'Personal website', type: 'url', placeholder: 'https://…', group: 'Contact & links', publicable: true },
  { key: 'resume_url', label: 'Resume URL', type: 'url', placeholder: 'Public link to a PDF resume', group: 'Contact & links', publicable: true },
  { key: 'years_experience', label: 'Total professional experience (years)', type: 'number', step: '0.5', placeholder: '0', group: 'Professional settings', publicable: true },
  { key: 'availability', label: 'Availability', type: 'text', placeholder: 'Open to internships / full-time roles', group: 'Professional settings', publicable: true },
];

function socialUsername(value, field) {
  const text = String(value ?? '');
  if (!field.prefix) return text;
  const prefixPath = field.key === 'github_url'
    ? /^(?:https?:\/\/)?(?:www\.)?github\.com\//i
    : /^(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\//i;
  return text.replace(prefixPath, '');
}

function savedSocialUrl(value, field) {
  const username = socialUsername(value, field).trim().replace(/^\/+|\/+$/g, '');
  return field.prefix && username ? `${field.prefix}${username}` : username;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [editing, setEditing] = useState({});
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const refs = useRef({});

  useEffect(() => { api('/admin/profile').then((data) => { setProfile(data); setDrafts(data); }).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, []);
  useEffect(() => { const field = Object.keys(editing).find((key) => editing[key]); if (field) refs.current[field]?.focus(); }, [editing]);

  const startEdit = (field) => { setDrafts((p) => ({ ...p, [field.key]: profile[field.key] ?? '' })); setEditing({ [field.key]: true }); setSuccess(''); };
  const cancelEdit = (field) => { setDrafts((p) => ({ ...p, [field.key]: profile[field.key] ?? '' })); setEditing((p) => ({ ...p, [field.key]: false })); };
  const saveField = async (field, isPublicOverride) => {
    setSaving((p) => ({ ...p, [field.key]: true })); setError(''); setSuccess('');
    try {
      const payload = { key: field.key, value: savedSocialUrl(drafts[field.key] ?? '', field) };
      if (typeof isPublicOverride === 'boolean') payload.is_public = isPublicOverride;
      const response = await api('/admin/profile', { method: 'PATCH', body: payload });
      setProfile(response.profile); setDrafts(response.profile); setEditing((p) => ({ ...p, [field.key]: false }));
      setSuccess(`${field.label} saved.`);
      if (response.index_warning) setError(response.index_warning);
    } catch (e) { setError(e.message || `Could not save ${field.label.toLowerCase()}.`); }
    finally { setSaving((p) => ({ ...p, [field.key]: false })); }
  };
  const toggleVisibility = async (field, checked) => {
    setSaving((p) => ({ ...p, [`visibility_${field.key}`]: true })); setError(''); setSuccess('');
    try {
      const response = await api('/admin/profile', { method: 'PATCH', body: { key: field.key, value: profile[field.key] ?? '', is_public: checked } });
      setProfile(response.profile); setDrafts(response.profile); setSuccess(`Visibility for ${field.label.toLowerCase()} updated.`);
      if (response.index_warning) setError(response.index_warning);
    } catch (e) { setError(e.message); }
    finally { setSaving((p) => ({ ...p, [`visibility_${field.key}`]: false })); }
  };

  if (loading) return <div className="admin-loading">Loading profile…</div>;
  if (!profile) return <div className="record-page profile-page"><ToastStack><Toast message={error || 'Profile could not be loaded.'} type="error" onDismiss={() => setError('')} /></ToastStack></div>;

  const groups = [...new Set(fields.map((f) => f.group))];
  return <div className="record-page profile-page">
    <div className="page-heading-row"><div><h1>Profile</h1><p className="page-subtitle">Edit each field independently. Fields are locked until you choose Edit, and changes are saved separately.</p></div><div className="page-heading-icon"><UserRound size={22} /></div></div>
    <div className="profile-callout"><Globe2 size={17} /><div><strong>Public visibility is controlled per field.</strong><p>Choose whether each profile field is visible to visitors and the public portfolio assistant.</p></div></div>
    <ToastStack><Toast message={success} type="success" onDismiss={() => setSuccess('')} /><Toast message={error} type="error" onDismiss={() => setError('')} /></ToastStack>
    <ResumeImport section="profile" onSaved={(result) => { setProfile(result.profile); setDrafts(result.profile); }} />
    {groups.map((group) => <section className="profile-section" key={group}><div className="section-heading"><div><h2>{group}</h2></div></div><div className="profile-field-list">
      {fields.filter((f) => f.group === group).map((field) => {
        const isEditing = Boolean(editing[field.key]);
        const isBusy = Boolean(saving[field.key]);
        const publicNow = (profile.public_fields || []).includes(field.key);
        const fieldValue = socialUsername(drafts[field.key], field);
        return <div className={`profile-field-row ${isEditing ? 'field-editing' : ''}`} key={field.key}>
        <div className="profile-field-label"><label htmlFor={`profile-${field.key}`}>{field.label}</label></div>
        <div className="profile-field-editor">{field.prefix && <span className="profile-url-prefix">{field.prefix}</span>}{field.type === 'textarea' ? <textarea id={`profile-${field.key}`} ref={(el) => { refs.current[field.key] = el; }} value={fieldValue ?? ''} rows={field.rows || 2} disabled={!isEditing || isBusy} placeholder={field.placeholder} onChange={(e) => setDrafts((p) => ({ ...p, [field.key]: e.target.value }))} /> : <input id={`profile-${field.key}`} ref={(el) => { refs.current[field.key] = el; }} type={field.type} step={field.step} min={field.type === 'number' ? 0 : undefined} value={fieldValue ?? ''} disabled={!isEditing || isBusy} placeholder={field.placeholder} onChange={(e) => setDrafts((p) => ({ ...p, [field.key]: e.target.value }))} />}
          <div className="profile-field-actions">{!isEditing ? <button className="small-action profile-edit-action" onClick={() => startEdit(field)}><Edit3 size={13} /> Edit</button> : <><button className="small-action muted-action" onClick={() => cancelEdit(field)} disabled={isBusy}>Cancel</button><button className="small-action primary-small-action" onClick={() => saveField(field)} disabled={isBusy} aria-busy={isBusy}>{isBusy ? <><LoaderCircle className="spin" size={13} /> Saving…</> : <><Save size={13} /> Save</>}</button></>}
            {field.publicable && <button className={`icon-button profile-visibility-action ${publicNow ? 'is-public' : ''}`} type="button" aria-label={`${saving[`visibility_${field.key}`] ? 'Updating visibility for' : publicNow ? 'Hide' : 'Show'} ${field.label} ${saving[`visibility_${field.key}`] ? '' : 'on public site'}`} title={`${publicNow ? 'Hide' : 'Show'} on public site`} aria-busy={Boolean(saving[`visibility_${field.key}`])} disabled={Boolean(saving[`visibility_${field.key}`]) || isEditing} onClick={() => toggleVisibility(field, !publicNow)}>{saving[`visibility_${field.key}`] ? <LoaderCircle className="spin" size={16} /> : publicNow ? <Eye size={16} /> : <EyeOff size={16} />}</button>}
          </div>
        </div>
        </div>;
      })}
    </div></section>)}
  </div>;
}
