import { useRef, useState } from 'react';
import { FileText, FileUp, LoaderCircle, Plus, RotateCcw, Save, Trash2 } from 'lucide-react';
import { api } from '../api';
import Toast, { ToastStack } from './Toast';

const profileFields = [
  { key: 'full_name', label: 'Full name' },
  { key: 'headline', label: 'Professional headline' },
  { key: 'email', label: 'Email', type: 'email' },
  { key: 'phone', label: 'Phone' },
  { key: 'location', label: 'Location' },
  { key: 'years_experience', label: 'Total experience (years)', type: 'number' },
  { key: 'objective', label: 'Career objective', multiline: true },
  { key: 'preferred_roles', label: 'Preferred roles', multiline: true },
  { key: 'github_url', label: 'GitHub URL', type: 'url' },
  { key: 'linkedin_url', label: 'LinkedIn URL', type: 'url' },
  { key: 'website_url', label: 'Personal website', type: 'url' },
  { key: 'resume_url', label: 'Resume URL', type: 'url' },
];

const recordFields = {
  skills: [
    { key: 'name', label: 'Skill name' },
    { key: 'category', label: 'Category' },
    { key: 'level', label: 'Proficiency level' },
    { key: 'years_experience', label: 'Years of experience', type: 'number' },
    { key: 'evidence', label: 'Evidence', multiline: true },
  ],
  education: [
    { key: 'institution', label: 'Institution' },
    { key: 'degree', label: 'Degree / qualification' },
    { key: 'stream', label: 'Stream / specialization' },
    { key: 'start_year', label: 'Start year', type: 'number' },
    { key: 'end_year', label: 'End year', type: 'number', hideWhenCurrent: true },
    { key: 'is_current', label: 'Currently studying', type: 'checkbox' },
    { key: 'grade_type', label: 'Grade format' },
    { key: 'grade_value', label: 'Grade / score' },
    { key: 'location', label: 'Location' },
    { key: 'description', label: 'Relevant coursework / details', multiline: true },
  ],
  projects: [
    { key: 'name', label: 'Project name' },
    { key: 'description', label: 'Description', multiline: true },
    { key: 'tech_stack', label: 'Technology stack', type: 'list' },
    { key: 'role', label: 'Your role' },
    { key: 'live_url', label: 'Live URL', type: 'url' },
    { key: 'github_url', label: 'GitHub URL', type: 'url' },
    { key: 'custom_fields', label: 'Resume links / other labeled details', type: 'customFields' },
  ],
  experience: [
    { key: 'company', label: 'Company / organization' },
    { key: 'title', label: 'Job title' },
    { key: 'employment_type', label: 'Employment type' },
    { key: 'location', label: 'Location' },
    { key: 'work_mode', label: 'Work mode' },
    { key: 'start_date', label: 'Start date', placeholder: 'MM/YYYY or DD/MM/YYYY' },
    { key: 'is_current', label: 'Currently working here', type: 'checkbox' },
    { key: 'end_date', label: 'End date', placeholder: 'MM/YYYY or DD/MM/YYYY', hideWhenCurrent: true },
    { key: 'description', label: 'Responsibilities / overview', multiline: true },
    { key: 'achievements', label: 'Achievements', type: 'list' },
    { key: 'tech_stack', label: 'Tools / technology', type: 'list' },
  ],
};

function PreviewField({ field, value, onChange, id }) {
  if (field.type === 'checkbox') {
    return <label className="resume-preview-checkbox" htmlFor={id}>
      <input id={id} type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
      <span>{field.label}</span>
    </label>;
  }
  if (field.type === 'customFields') {
    const rows = Array.isArray(value) ? value : [];
    return <div className="resume-custom-fields">
      <span className="resume-field-label">{field.label}</span>
      {rows.map((row, index) => <div className="resume-link-edit-row" key={`${id}-${index}`}>
        <input aria-label={`Link heading ${index + 1}`} placeholder="Link heading (e.g. GitHub)" value={row.type || ''} onChange={(event) => onChange(rows.map((item, rowIndex) => rowIndex === index ? { ...item, type: event.target.value } : item))} />
        <input aria-label={`Link URL ${index + 1}`} type="url" placeholder="https://…" value={row.value || ''} onChange={(event) => onChange(rows.map((item, rowIndex) => rowIndex === index ? { ...item, value: event.target.value } : item))} />
        <button type="button" className="icon-button" aria-label="Remove resume link" onClick={() => onChange(rows.filter((_, rowIndex) => rowIndex !== index))}><Trash2 size={14} /></button>
      </div>)}
      <button type="button" className="text-button resume-add-link" onClick={() => onChange([...rows, { type: '', value: '' }])}><Plus size={14} /> Add labeled link</button>
    </div>;
  }
  if (field.type === 'list') {
    return <label className="resume-preview-field">
      <span>{field.label}</span>
      <textarea rows={3} value={(Array.isArray(value) ? value : []).join('\n')} placeholder="One item per line" onChange={(event) => onChange(event.target.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean))} />
    </label>;
  }
  const controlProps = {
    id,
    value: value ?? '',
    placeholder: field.placeholder || '',
    onChange: (event) => onChange(field.type === 'number' ? (event.target.value === '' ? null : Number(event.target.value)) : event.target.value),
  };
  return <label className={`resume-preview-field ${field.multiline ? 'resume-preview-field-wide' : ''}`} htmlFor={id}>
    <span>{field.label}</span>
    {field.multiline ? <textarea {...controlProps} rows={3} /> : <input {...controlProps} type={field.type || 'text'} />}
  </label>;
}

export default function ResumeImport({ onSaved, section = 'all' }) {
  const [file, setFile] = useState(null);
  const fileInputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const updateProfile = (key, value) => setPreview((current) => ({ ...current, profile: { ...current.profile, [key]: value } }));
  const updateRow = (section, index, key, value) => setPreview((current) => ({
    ...current,
    [section]: current[section].map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row),
  }));
  const removeRow = (section, index) => setPreview((current) => ({
    ...current,
    [section]: current[section].filter((_, rowIndex) => rowIndex !== index),
  }));

  const parseResume = async (selectedFile = file) => {
    if (!selectedFile) { setError('Choose a PDF or DOCX resume first.'); return; }
    setParsing(true); setPreview(null); setError(''); setNotice('');
    try {
      const body = new FormData();
      body.append('file', selectedFile);
      if (section !== 'all') body.append('section', section);
      const result = await api('/admin/resume/parse', { method: 'POST', body });
      if (!result.data || typeof result.data !== 'object') throw new Error('The parser returned no reviewable resume details.');
      setPreview(result.data);
    } catch (requestError) {
      setError(requestError.message || 'Could not parse this resume.');
    } finally {
      setParsing(false);
    }
  };

  const saveResume = async () => {
    if (!preview) return;
    setSaving(true); setError(''); setNotice('');
    try {
      const result = await api('/admin/resume/import', { method: 'POST', body: preview });
      onSaved?.(result);
      const count = Object.values(result.counts || {}).reduce((sum, value) => sum + value, 0);
      setNotice(section === 'profile' ? result.message : `${result.message} Added ${count} portfolio records.`);
      if (result.index_warning) setError(result.index_warning);
      setPreview(null); setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (requestError) {
      setError(requestError.message || 'Could not save the reviewed resume details.');
    } finally {
      setSaving(false);
    }
  };

  const cancelPreview = () => { setPreview(null); setError(''); setNotice(''); };
  const previewSections = section === 'all' ? Object.keys(recordFields) : [section].filter((key) => key in recordFields);
  const includesProfile = section === 'all' || section === 'profile';
  const hasPreviewContent = Boolean(preview && (
    (includesProfile && Object.values(preview.profile || {}).some((value) => value !== '' && value !== null && value !== undefined))
    || previewSections.some((key) => preview[key]?.some((row) => Object.values(row).some((value) => value !== '' && value !== null && value !== undefined && value !== false && (!Array.isArray(value) || value.length))))
  ));
  const importDescription = section === 'all'
    ? 'Extract profile details, skills, education, experience, projects, and labeled links for review.'
    : `Extract only ${section === 'profile' ? 'profile details' : section} from the uploaded resume for review.`;

  return <section className="resume-import-panel">
    <div className="resume-import-heading">
      <div className="resume-import-icon"><FileText size={18} /></div>
      <div><h2>Import from resume</h2><p>{importDescription}</p></div>
    </div>
    {!preview ? <>
      <div className="resume-upload-controls">
        <label className="resume-file-picker" htmlFor="resume-upload"><FileUp size={16} /><span>{file?.name || 'Choose a PDF or DOCX file'}</span><input ref={fileInputRef} id="resume-upload" type="file" disabled={parsing} accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => { const selectedFile = event.target.files?.[0] || null; setFile(selectedFile); setError(''); setNotice(''); if (selectedFile) parseResume(selectedFile); }} /></label>
        <button type="button" className="primary-button" onClick={parseResume} disabled={!file || parsing}>{parsing ? <><LoaderCircle className="spin" size={15} /> Processing resume…</> : <><FileUp size={15} /> Parse resume</>}</button>
      </div>
      <p className="resume-import-hint">Use a text-based PDF or DOCX. Scanned/image-only PDFs require OCR. Nothing is saved until you confirm the preview.</p>
    </> : <>
      <div className="resume-preview-notice"><strong>Review before saving.</strong> Extracted details may need correction. {section === 'profile' ? 'Non-empty profile values will be updated; existing public-visibility settings are unchanged.' : `Only reviewed ${section} records will be added; existing records will not be deleted.`}</div>
      {includesProfile && <section className="resume-preview-section">
        <div className="resume-preview-section-heading"><h3>Profile</h3></div>
        <div className="resume-preview-grid">
          {profileFields.map((field) => <PreviewField key={field.key} id={`resume-profile-${field.key}`} field={field} value={preview.profile?.[field.key]} onChange={(value) => updateProfile(field.key, value)} />)}
        </div>
      </section>}
      {previewSections.map((recordSection) => {
        const fields = recordFields[recordSection];
        return <section className="resume-preview-section" key={recordSection}>
        <div className="resume-preview-section-heading"><h3>{recordSection} <span>{preview[recordSection]?.length || 0}</span></h3></div>
        {preview[recordSection]?.length ? <div className="resume-preview-records">{preview[recordSection].map((row, index) => <article className="resume-preview-record" key={`${recordSection}-${index}`}>
          <div className="resume-preview-record-heading"><strong>{row.name || row.institution || row.title || row.company || `${recordSection} record ${index + 1}`}</strong><button type="button" className="small-action danger-action" onClick={() => removeRow(recordSection, index)}><Trash2 size={13} /> Remove</button></div>
          <div className="resume-preview-grid">
            {fields.filter((field) => !(field.hideWhenCurrent && row.is_current)).map((field) => <PreviewField key={field.key} id={`resume-${recordSection}-${index}-${field.key}`} field={field} value={row[field.key]} onChange={(value) => updateRow(recordSection, index, field.key, value)} />)}
          </div>
        </article>)}</div> : <p className="resume-empty-section">No {section} records were detected.</p>}
      </section>;
      })}
      {!hasPreviewContent && <p className="resume-empty-section">No resume details could be identified. Try a clearer text-based PDF or DOCX file.</p>}
      <div className="resume-preview-actions"><button type="button" className="secondary-button" onClick={cancelPreview} disabled={saving}><RotateCcw size={14} /> Discard preview</button><button type="button" className="primary-button" onClick={saveResume} disabled={saving || !hasPreviewContent}>{saving ? <><LoaderCircle className="spin" size={15} /> Saving…</> : <><Save size={15} /> Save reviewed details</>}</button></div>
    </>}
    <ToastStack><Toast message={notice} type="success" onDismiss={() => setNotice('')} /><Toast message={error} type="error" onDismiss={() => setError('')} /></ToastStack>
  </section>;
}
