import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowUpRight, Briefcase, Code2, Edit3, FilePlus2, Folder, GraduationCap, LoaderCircle, Plus, Save, Search, Trash2, X } from 'lucide-react';
import { api } from '../../api';
import ResumeImport from '../../components/ResumeImport';
import Toast, { ToastStack } from '../../components/Toast';

const initialValue = (field) => {
  if (field.type === 'checkbox') return false;
  if (field.type === 'list') return '';
  if (field.type === 'customFields') return [{ type: '', value: '' }];
  if (field.name === 'level') return 'Beginner';
  if (field.name === 'employment_type') return 'Internship';
  if (field.name === 'grade_type') return 'CGPA';
  return '';
};

function blankRecord(schema) {
  return Object.fromEntries(schema.fields.map((field) => [field.name, initialValue(field)]));
}

function toFormRecord(schema, item) {
  const data = blankRecord(schema);
  for (const field of schema.fields) {
    const value = item?.[field.name];
    if (value === undefined || value === null) continue;
    if (field.type === 'list') data[field.name] = Array.isArray(value) ? value.join(', ') : String(value);
    else if (field.type === 'customFields') data[field.name] = Array.isArray(value) && value.length ? value : [{ type: '', value: '' }];
    else data[field.name] = value;
  }
  return data;
}

function toPayload(schema, form) {
  const body = { ...form };
  for (const field of schema.fields) {
    if (field.type === 'list') body[field.name] = String(form[field.name] || '').split(/[\n,]/).map((x) => x.trim()).filter(Boolean);
    if (field.type === 'number' && form[field.name] !== '') body[field.name] = Number(form[field.name]);
    if (field.type === 'number' && form[field.name] === '') body[field.name] = null;
    if (field.name === 'is_current' && form.is_current) {
      if ('end_year' in body) body.end_year = null;
      if (schema.endpoint === '/admin/experience') body.end_date = '';
    }
  }
  if (schema.endpoint === '/admin/education' && body.is_current) body.end_year = null;
  return body;
}

export default function RecordManager({ schema }) {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(() => blankRecord(schema));
  const [editingId, setEditingId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [query, setQuery] = useState('');
  const [categories, setCategories] = useState([]);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [deleteId, setDeleteId] = useState(null);
  const [deletingRecord, setDeletingRecord] = useState(false);
  const [deleteSelectedConfirm, setDeleteSelectedConfirm] = useState(false);
  const [deletingSelected, setDeletingSelected] = useState(false);
  const [deleteAllConfirm, setDeleteAllConfirm] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);

  const loadItems = async () => {
    const result = await api(schema.endpoint);
    setItems(Array.isArray(result) ? result : []);
    setSelectedIds(new Set());
  };
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    setSelectedIds(new Set());
    const loadPage = async () => {
      const loads = [api(schema.endpoint).then((result) => {
        if (active) setItems(Array.isArray(result) ? result : []);
      }).catch((err) => {
        if (active) setError(err.message);
      })];
      if (schema.endpoint === '/admin/skills') {
        loads.push(api('/admin/skill-types').then((data) => {
          if (active) setCategories(data.types || []);
        }).catch((err) => {
          if (active) setError(`Skill categories could not be loaded: ${err.message}`);
        }));
      }
      await Promise.all(loads);
      if (active) setLoading(false);
    };
    loadPage();
    return () => { active = false; };
  }, [schema.endpoint]);

  const visibleItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => Object.values(item).some((v) => (Array.isArray(v) ? JSON.stringify(v) : String(v ?? '')).toLowerCase().includes(q)));
  }, [items, query]);
  const allVisibleSelected = visibleItems.length > 0 && visibleItems.every((item) => selectedIds.has(item.id));
  const selectVisible = (checked) => setSelectedIds((previous) => {
    const next = new Set(previous);
    visibleItems.forEach((item) => checked ? next.add(item.id) : next.delete(item.id));
    return next;
  });
  const toggleSelected = (id, checked) => setSelectedIds((previous) => {
    const next = new Set(previous);
    if (checked) next.add(id);
    else next.delete(id);
    return next;
  });

  const beginCreate = () => { setEditingId(null); setForm(blankRecord(schema)); setShowForm(true); setError(''); setNotice(''); };
  const beginEdit = (item) => { setEditingId(item.id); setForm(toFormRecord(schema, item)); setShowForm(true); setError(''); setNotice(''); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  const closeForm = () => { setShowForm(false); setEditingId(null); setForm(blankRecord(schema)); setError(''); };
  const change = (name, value) => setForm((prev) => ({ ...prev, [name]: value }));

  const save = async (event) => {
    event.preventDefault(); setSaving(true); setError(''); setNotice('');
    for (const field of schema.fields.filter((f) => f.required)) {
      const value = form[field.name];
      if (value === undefined || value === null || String(value).trim() === '') {
        setError(`${field.label} is required.`); setSaving(false); return;
      }
    }
    try {
      const payload = toPayload(schema, form);
      const result = editingId
        ? await api(`${schema.endpoint}/${editingId}`, { method: 'PUT', body: payload })
        : await api(schema.endpoint, { method: 'POST', body: payload });
      await loadItems(); closeForm();
      setNotice(editingId ? `${schema.singular[0].toUpperCase() + schema.singular.slice(1)} updated.` : `${schema.singular[0].toUpperCase() + schema.singular.slice(1)} added.`);
      if (result.index_warning) setError(result.index_warning);
    } catch (err) { setError(err.message || 'Could not save this record.'); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!deleteId) return;
    setDeletingRecord(true);
    setError(''); setNotice('');
    try {
      const result = await api(`${schema.endpoint}/${deleteId}`, { method: 'DELETE' });
      setNotice(`${schema.singular[0].toUpperCase() + schema.singular.slice(1)} deleted.`);
      if (result.index_warning) setError(result.index_warning);
      try {
        await loadItems();
      } catch (err) {
        setError(`Record was deleted, but the list could not be refreshed: ${err.message}`);
      }
    } catch (err) { setError(err.message || 'Could not delete the record.'); }
    finally { setDeletingRecord(false); setDeleteId(null); }
  };

  const removeSelected = async () => {
    if (!selectedIds.size) return;
    if (selectedIds.size > 500) {
      setError('Select no more than 500 records per batch.');
      return;
    }
    setDeletingSelected(true); setError(''); setNotice('');
    try {
      const result = await api(`${schema.endpoint}/bulk`, {
        method: 'DELETE',
        body: { ids: [...selectedIds] },
      });
      setSelectedIds(new Set());
      setNotice(result.message || `Deleted ${result.deleted} ${schema.title.toLowerCase()} record(s).`);
      if (result.index_warning) setError(result.index_warning);
      try {
        await loadItems();
      } catch (err) {
        setError(`Selected records were deleted, but the list could not be refreshed: ${err.message}`);
      }
      setDeleteSelectedConfirm(false);
    } catch (err) {
      setError(err.message || `Could not delete the selected ${schema.title.toLowerCase()}.`);
    } finally {
      setDeletingSelected(false);
    }
  };

  const removeAll = async () => {
    setDeletingAll(true); setError(''); setNotice('');
    try {
      const result = await api(schema.endpoint, { method: 'DELETE' });
      setDeleteAllConfirm(false);
      setSelectedIds(new Set());
      setItems([]);
      setNotice(result.message || `All ${schema.title.toLowerCase()} deleted.`);
      if (result.index_warning) setError(result.index_warning);
      if (result.reindex_job?.id) {
        window.dispatchEvent(new CustomEvent('folioport:reindex-job', {
          detail: { id: result.reindex_job.id },
        }));
      }
      try {
        await loadItems();
      } catch (err) {
        setError(`Records were deleted, but the list could not be refreshed: ${err.message}`);
      }
    } catch (err) {
      setError(err.message || `Could not delete all ${schema.title.toLowerCase()}.`);
    } finally {
      setDeletingAll(false);
    }
  };

  const refreshAfterResumeImport = () => {
    loadItems().catch((err) => setError(`Resume details were saved, but the list could not be refreshed: ${err.message}`));
  };
  const RecordIcon = schema.endpoint === '/admin/skills'
    ? Code2
    : schema.endpoint === '/admin/education'
      ? GraduationCap
      : schema.endpoint === '/admin/projects'
        ? Folder
        : Briefcase;
  const categoryOptions = [...new Set([
    'Programming', 'Frontend', 'Backend', 'Database', 'DevOps', 'AI / ML',
    'Testing', 'Tools', 'Core Concepts', 'Soft skills', 'Other',
    ...categories,
    form.category,
  ].filter(Boolean))];

  if (loading) return <div className="admin-loading">Loading {schema.title.toLowerCase()}…</div>;

  return <div className="record-page">
    <div className="page-heading-row"><div><h1>{schema.title}</h1><p className="page-subtitle">{schema.subtitle}</p></div><div className="page-heading-icon"><Code2 size={22} /></div></div>
    <ToastStack><Toast message={notice} type="success" onDismiss={() => setNotice('')} /><Toast message={error} type="error" onDismiss={() => setError('')} /></ToastStack>
    <ResumeImport section={schema.endpoint.slice('/admin/'.length)} onSaved={refreshAfterResumeImport} />

    {showForm && <div className="modal-backdrop" role="presentation"><section className="record-form-card record-form-modal" role="dialog" aria-modal="true" aria-labelledby="record-form-title"><div className="record-form-heading"><div><p className="eyebrow">{editingId ? 'UPDATE RECORD' : 'NEW RECORD'}</p><h2 id="record-form-title">{editingId ? `Edit ${schema.singular}` : `Add ${schema.singular}`}</h2></div><button className="icon-button" type="button" onClick={closeForm} aria-label="Close form"><X size={18} /></button></div>
      <form onSubmit={save} className="record-form-grid">
        {schema.fields.map((field) => {
          if (field.hideWhenCurrent && form.is_current) return null;
          const value = form[field.name] ?? '';
          if (field.type === 'customFields') return <div className="form-field full-width" key={field.name}><label>{field.label}</label><div className="custom-fields-editor">{(Array.isArray(value) ? value : []).map((row, index) => <div className="custom-field-row" key={index}><input value={row.type || ''} aria-label={`Custom field ${index + 1} type`} placeholder="Key / type (e.g. Demo)" onChange={(e) => change(field.name, value.map((x, i) => i === index ? { ...x, type: e.target.value } : x))} /><input value={row.value || ''} aria-label={`Custom field ${index + 1} value`} placeholder="Value (e.g. Hosted on Render)" onChange={(e) => change(field.name, value.map((x, i) => i === index ? { ...x, value: e.target.value } : x))} /><button type="button" className="icon-button small-icon" aria-label="Remove custom field" onClick={() => change(field.name, value.filter((_, i) => i !== index))}><X size={14} /></button></div>)}<button type="button" className="text-button add-custom-row" onClick={() => change(field.name, [...(Array.isArray(value) ? value : []), { type: '', value: '' }])}><Plus size={14} /> Add key/value pair</button></div></div>;
                if (field.type === 'checkbox') return <label className="form-checkbox-row" key={field.name}><input type="checkbox" checked={Boolean(value)} onChange={(e) => change(field.name, e.target.checked)} /><span><strong>{field.label}</strong></span></label>;
          if (field.type === 'list') return <div className={`form-field ${field.name === 'highlights' ? 'full-width' : ''}`} key={field.name}><label htmlFor={`record-${field.name}`}>{field.label}{field.required && <span className="required-star"> *</span>}</label><textarea id={`record-${field.name}`} rows={2} value={value} placeholder={field.placeholder || 'Separate items with commas or new lines'} onChange={(e) => change(field.name, e.target.value)} /></div>;
          if (field.type === 'textarea') return <div className="form-field full-width" key={field.name}><label htmlFor={`record-${field.name}`}>{field.label}{field.required && <span className="required-star"> *</span>}</label><textarea id={`record-${field.name}`} rows={field.rows || 3} required={field.required} value={value} placeholder={field.placeholder || ''} onChange={(e) => change(field.name, e.target.value)} /></div>;
          if (field.type === 'select') return <div className="form-field" key={field.name}><label htmlFor={`record-${field.name}`}>{field.label}{field.required && <span className="required-star"> *</span>}</label><select id={`record-${field.name}`} value={value} onChange={(e) => change(field.name, e.target.value)}>{(field.options || []).map((option) => <option key={option || 'blank'} value={option}>{option || 'Not specified'}</option>)}</select></div>;
          if (field.type === 'category') return <div className="form-field" key={field.name}><label htmlFor={`record-${field.name}`}>{field.label}{field.required && <span className="required-star"> *</span>}</label><select id={`record-${field.name}`} required={field.required} value={value} onChange={(e) => change(field.name, e.target.value)}><option value="" disabled>Select a category</option>{categoryOptions.map((category) => <option key={category} value={category}>{category}</option>)}</select></div>;
          return <div className="form-field" key={field.name}><label htmlFor={`record-${field.name}`}>{field.label}{field.required && <span className="required-star"> *</span>}</label><input id={`record-${field.name}`} type={field.type || 'text'} required={field.required} min={field.min} max={field.max} step={field.step} value={value} placeholder={field.placeholder || ''} onChange={(e) => change(field.name, e.target.value)} /></div>;
        })}
        <div className="record-form-actions full-width"><button type="button" className="secondary-button" onClick={closeForm} disabled={saving}>Cancel</button><button type="submit" className="primary-button" disabled={saving} aria-busy={saving}>{saving ? <><LoaderCircle className="spin" size={15} /> Saving…</> : <><Save size={15} /> Save {schema.singular}</>}</button></div>
      </form>
    </section></div>}

    <div className="record-list-toolbar"><div><strong>{items.length}</strong><span> {items.length === 1 ? schema.singular : `${schema.title.toLowerCase()} records`}</span></div><div className="record-toolbar-actions"><label className="record-search"><Search size={15} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={`Search ${schema.title.toLowerCase()}…`} /></label>{visibleItems.length > 0 && <label className="record-select-all"><input type="checkbox" checked={allVisibleSelected} onChange={(event) => selectVisible(event.target.checked)} disabled={deletingSelected || deletingAll} /> Select visible</label>}{selectedIds.size > 0 && <button type="button" className="danger-button delete-selected-button" onClick={() => setDeleteSelectedConfirm(true)} disabled={deletingSelected || deletingAll}><Trash2 size={14} /> Delete selected ({selectedIds.size})</button>}{!showForm && items.length > 0 && <button type="button" className="danger-button delete-all-button" onClick={() => { setDeleteAllConfirm(true); setError(''); setNotice(''); }} disabled={deletingAll || deletingSelected}><Trash2 size={14} /> Delete all</button>}{!showForm && <button type="button" className="primary-button add-record-button" onClick={beginCreate}><Plus size={16} /> Add {schema.singular}</button>}</div></div>

    {visibleItems.length === 0 ? <div className="empty-state"><div className="empty-state-icon"><FilePlus2 size={22} /></div><h3>{items.length ? 'No matching records' : `No ${schema.title.toLowerCase()} added yet`}</h3><p>{items.length ? 'Try a different search term.' : `Start by adding your first ${schema.singular}. Well-described records improve the AI portfolio and job-fit analysis.`}</p>{!items.length && <button className="primary-button" onClick={beginCreate}><Plus size={16} /> Add {schema.singular}</button>}</div> : <div className="record-card-list">
      {visibleItems.map((item) => <article className={`portfolio-record-card ${selectedIds.has(item.id) ? 'record-selected' : ''}`} key={item.id}><div className="record-card-top"><label className="record-select-control" aria-label={`Select ${item.name || item.institution || item.company || item.title || schema.singular}`}><input type="checkbox" checked={selectedIds.has(item.id)} onChange={(event) => toggleSelected(item.id, event.target.checked)} disabled={deletingSelected || deletingAll} /></label><div className="record-type-icon" aria-hidden="true" title={item.name || item.institution || item.company || item.title}><RecordIcon size={16} /></div><div className="record-card-heading"><h3>{item.name || item.institution || item.title || item.company || 'Untitled record'}</h3><p>{schema.summary ? schema.summary(item) : ''}</p></div></div>
        {item.description && <p className="record-card-description">{item.description}</p>}
        {schema.endpoint === '/admin/skills' && item.evidence && <div className="record-evidence"><strong>Evidence</strong><p>{item.evidence}</p></div>}
        {schema.endpoint === '/admin/projects' && item.custom_fields?.length > 0 && <div className="custom-field-display">{item.custom_fields.map((x, i) => <span key={i}><b>{x.type}:</b> {x.value}</span>)}</div>}
        {schema.endpoint === '/admin/projects' && <div className="record-card-links">{item.github_url && <a href={item.github_url} target="_blank" rel="noreferrer">GitHub <ArrowUpRight size={13} /></a>}{item.live_url && <a href={item.live_url} target="_blank" rel="noreferrer">Live demo <ArrowUpRight size={13} /></a>}</div>}
        {schema.endpoint === '/admin/experience' && item.achievements?.length > 0 && <ul className="record-achievements">{item.achievements.slice(0, 3).map((x, i) => <li key={i}>{x}</li>)}</ul>}
        {(item.tech_stack?.length > 0 || item.keywords?.length > 0) && <div className="record-tag-list">{(item.tech_stack || item.keywords || []).map((tag) => <span key={tag}>{tag}</span>)}</div>}
        <div className="record-card-footer"><span className="record-updated">Updated {item.updated_at ? new Date(item.updated_at).toLocaleDateString() : '—'}</span><div><button type="button" className="small-action" onClick={() => beginEdit(item)} disabled={deletingSelected || deletingAll}><Edit3 size={13} /> Edit</button><button type="button" className="small-action danger-action" onClick={() => setDeleteId(item.id)} disabled={deletingSelected || deletingAll}><Trash2 size={13} /> Delete</button></div></div>
      </article>)}
    </div>}

    {deleteId && <div className="modal-backdrop" role="presentation" onClick={() => { if (!deletingRecord) setDeleteId(null); }}><div className="confirm-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}><div className="confirm-icon"><AlertTriangle size={21} /></div><h2>Delete this {schema.singular}?</h2><p>This action cannot be undone. Related search-index entries will also be removed when the index is reachable.</p><div className="confirm-actions"><button className="secondary-button" onClick={() => setDeleteId(null)} disabled={deletingRecord}>Cancel</button><button className="danger-button" onClick={remove} disabled={deletingRecord} aria-busy={deletingRecord}>{deletingRecord ? <><LoaderCircle className="spin" size={15} /> Deleting…</> : <><Trash2 size={15} /> Delete permanently</>}</button></div></div></div>}
    {deleteSelectedConfirm && <div className="modal-backdrop" role="presentation" onClick={() => { if (!deletingSelected) setDeleteSelectedConfirm(false); }}><section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-selected-title" onClick={(event) => event.stopPropagation()}><div className="confirm-icon"><AlertTriangle size={21} /></div><h2 id="delete-selected-title">Delete {selectedIds.size} selected {selectedIds.size === 1 ? schema.singular : schema.title.toLowerCase()}?</h2><p>This permanently deletes the selected records, including any selected records hidden by the current search. This cannot be undone.</p><div className="confirm-actions"><button className="secondary-button" type="button" onClick={() => setDeleteSelectedConfirm(false)} disabled={deletingSelected}>Cancel</button><button className="danger-button" type="button" onClick={removeSelected} disabled={deletingSelected} aria-busy={deletingSelected}>{deletingSelected ? <><LoaderCircle className="spin" size={15} /> Deleting…</> : <><Trash2 size={15} /> Delete selected</>}</button></div></section></div>}
    {deleteAllConfirm && <div className="modal-backdrop" role="presentation" onClick={() => { if (!deletingAll) setDeleteAllConfirm(false); }}><section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-all-title" onClick={(event) => event.stopPropagation()}><div className="confirm-icon"><AlertTriangle size={21} /></div><h2 id="delete-all-title">Delete all {schema.title.toLowerCase()}?</h2><p>This permanently deletes all {items.length} {schema.title.toLowerCase()} records, including records hidden by the current search. This cannot be undone.</p><div className="confirm-actions"><button className="secondary-button" type="button" onClick={() => setDeleteAllConfirm(false)} disabled={deletingAll}>Cancel</button><button className="danger-button" type="button" onClick={removeAll} disabled={deletingAll}>{deletingAll ? <><LoaderCircle className="spin" size={15} /> Deleting…</> : <><Trash2 size={15} /> Delete all</>}</button></div></section></div>}
  </div>;
}
