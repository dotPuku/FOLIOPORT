import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, BriefcaseBusiness, Check, CheckCircle2, ChevronDown, FileText, LoaderCircle, Moon, Plus, Sparkles, Sun, UploadCloud, X, XCircle } from 'lucide-react';
import { api } from '../api';
import Toast, { ToastStack } from '../components/Toast';
import useScrollHeader from '../useScrollHeader';

const pct = (n) => `${Math.max(0, Math.min(100, Number(n) || 0))}%`;
const statusLabel = { matched: 'Matched', related: 'Related evidence', unmatched: 'Gap' };

function SkillGroup({ title, items, tone }) {
  if (!items?.length) return null;
  const Icon = tone === 'good' ? CheckCircle2 : tone === 'related' ? Sparkles : XCircle;
  return <section className={`result-skill-group ${tone}`}>
    <div className="result-group-heading"><Icon size={17} /><h3>{title}</h3><span>{items.length}</span></div>
    <div className="skill-result-list">
      {items.map((item) => <div className="skill-result-item" key={`${item.skill}-${item.status}`}>
        <div className="skill-result-main"><span className="skill-result-name">{item.skill}</span><span className={`skill-status ${item.status}`}>{statusLabel[item.status] || item.status}</span></div>
        {item.evidence?.length > 0 && <p className="evidence-text">{item.evidence.slice(0, 2).map((e) => `${e.title}: ${e.evidence || e.text || ''}`).join(' · ')}</p>}
        {!item.evidence?.length && item.related_evidence?.length > 0 && <p className="evidence-text">Related: {item.related_evidence[0].title}{item.related_evidence[0].text ? ` — ${item.related_evidence[0].text}` : ''}{Number.isFinite(item.related_evidence[0].score) ? ` (vector similarity ${Math.round(item.related_evidence[0].score * 100)}%; retrieval signal, not a probability)` : ''}</p>}
        {!item.evidence?.length && !item.related_evidence?.length && item.job_evidence && <p className="evidence-text">Job requirement: {item.job_evidence}</p>}
      </div>)}
    </div>
  </section>;
}

function ScoreRing({ score }) {
  const hasScore = Number.isFinite(score);
  const style = { '--score-angle': `${hasScore ? Math.max(0, Math.min(100, score)) * 3.6 : 0}deg` };
  return <div className="score-ring" style={style}><div className="score-ring-inner"><strong>{hasScore ? `${score}%` : '—'}</strong><span>{hasScore ? 'overall fit' : 'not scored'}</span></div></div>;
}

export default function JobMatcher({ theme, setTheme }) {
  const [description, setDescription] = useState('');
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileInput = useRef(null);
  const headerVisible = useScrollHeader();

  const reset = () => { setResult(null); setDescription(''); setFile(null); setError(''); if (fileInput.current) fileInput.current.value = ''; };

  const analyze = async (event) => {
    event?.preventDefault();
    if (!file && description.trim().length < 80) { setError('Paste a complete job description (at least 80 characters) or upload a PDF, DOC, DOCX, or TXT file.'); return; }
    setBusy(true); setError(''); setResult(null);
    try {
      let data;
      if (file) {
        const form = new FormData(); form.append('file', file); form.append('job_description', description);
        data = await api('/job-match', { method: 'POST', body: form });
      } else data = await api('/job-match', { method: 'POST', body: { job_description: description } });
      setResult(data);
    } catch (err) { setError(err.message || 'Analysis failed. Please check the file and retry.'); }
    finally { setBusy(false); }
  };

  return <div className="matcher-page">
    <header className={`matcher-topbar sticky-page-header scroll-aware-header ${headerVisible ? '' : 'scroll-aware-header-hidden'}`}>
      <div className="matcher-brand"><Link className="brand-lockup" to="/"><span className="brand-mark">f.</span><span>folioport</span></Link><span className="brand-divider" /><span className="page-crumb">Job matcher</span></div>
      <div className="matcher-actions"><Link to="/" className="back-to-chat"><ArrowLeft size={15} /> AI portfolio</Link><button className="icon-button" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">{theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}</button></div>
    </header>
    <main className="matcher-container">
      {!result ? <>
        <div className="matcher-intro"><div className="matcher-icon"><BriefcaseBusiness size={22} /></div><p className="eyebrow">CAREER TOOL · EVIDENCE-BASED</p><h1>See how you fit the role.</h1><p>Paste a job description or upload a file. FOLIOPORT compares requirements against your profile, skills, projects, education, and experience stored in the portfolio.</p></div>
        <form className="jd-form" onSubmit={analyze}>
          <label className="field-label" htmlFor="job-description">Job description <span className="label-optional">Paste text or upload a document</span></label>
          <textarea id="job-description" className="jd-textarea" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Paste the full job description here — responsibilities, required skills, experience, education…" rows={11} maxLength={45000} disabled={Boolean(file)} />
          <div className="jd-form-bottom"><span className="char-count">{description.length.toLocaleString()} / 45,000 characters</span><span className="or-divider">OR</span><button type="button" className="upload-trigger" onClick={() => fileInput.current?.click()}><UploadCloud size={17} /> Upload JD</button><input ref={fileInput} hidden type="file" accept=".txt,.pdf,.doc,.docx,text/plain,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(e) => { const nextFile = e.target.files?.[0] || null; setFile(nextFile); setError(''); if (nextFile) setDescription(''); }} /></div>
          {file && <div className="selected-file"><FileText size={16} /><span><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(0)} KB · Ready to analyse</small></span><button type="button" aria-label="Remove file" className="icon-button small-icon" onClick={() => { setFile(null); if (fileInput.current) fileInput.current.value = ''; }}><X size={15} /></button></div>}
          <ToastStack><Toast message={error} type="error" onDismiss={() => setError('')} /></ToastStack>
          <div className="analyze-row"><span className="privacy-note"><Check size={14} /> No resume upload needed — your saved portfolio is used.</span><button type="submit" className="primary-button" disabled={busy}>{busy ? <><LoaderCircle className="spin" size={17} /> Analysing…</> : <>Analyse job fit <ArrowRight size={17} /></>}</button></div>
        </form>
        <div className="matcher-footnotes"><div><span className="footnote-number">01</span><div><strong>Requirements extracted</strong><p>AI structures the job description into required and preferred skills.</p></div></div><div><span className="footnote-number">02</span><div><strong>Portfolio evidence searched</strong><p>SQL records and semantic retrieval surface supporting evidence.</p></div></div><div><span className="footnote-number">03</span><div><strong>Score calculated transparently</strong><p>Exact matches and related evidence are distinguished; gaps stay visible.</p></div></div></div>
      </> : <div className="match-results">
        <button className="text-button" onClick={reset}><ArrowLeft size={15} /> Analyse another job</button>
        <div className="result-header"><div><p className="eyebrow">JOB FIT REPORT</p><h1>{result.job?.title || 'Job description analysis'}</h1><p className="result-company">{result.job?.company || 'Company not identified'}{result.job?.seniority ? ` · ${result.job.seniority}` : ''}</p><p className="result-summary">{result.job?.summary}</p></div><div className="result-score-block"><ScoreRing score={result.score} /><span className={`score-label ${result.score >= 75 ? 'high' : result.score >= 50 ? 'medium' : 'low'}`}>{result.score_label}</span></div></div>
        <div className="result-stats-row"><div><strong>{result.matched_skills?.length || 0}</strong><span>Confirmed matches</span></div><div><strong>{result.related_skills?.length || 0}</strong><span>Related evidence</span></div><div><strong>{result.unmatched_skills?.length || 0}</strong><span>Skill gaps</span></div></div>
        <section className="breakdown-card"><div className="section-heading"><div><p className="eyebrow">SCORE BREAKDOWN</p><h2>What makes up your score</h2></div><span className="detail-note">Weighted, normalized components</span></div>
          {Object.entries(result.score_breakdown || {}).length ? Object.entries(result.score_breakdown || {}).map(([key, value]) => <div className="breakdown-row" key={key}><div className="breakdown-label"><span>{key.replaceAll('_', ' ').replace(/\b\w/g, (x) => x.toUpperCase())}</span><strong>{value}%</strong></div><div className="breakdown-track"><div className="breakdown-fill" style={{ width: pct(value) }} /></div></div>) : <p className="evidence-text">No measurable scoring criteria were identified in this job description.</p>}
        </section>
        <div className="skill-results-columns"><SkillGroup title="Matched skills" items={result.matched_skills} tone="good" /><SkillGroup title="Related evidence" items={result.related_skills} tone="related" /><SkillGroup title="Skills to build / evidence" items={result.unmatched_skills} tone="gap" /></div>
        <section className="report-card"><div className="report-icon"><Sparkles size={18} /></div><div><p className="eyebrow">CAREER COACH NOTES</p><h2>How to strengthen your application</h2><p className="report-summary">{result.report?.summary}</p><div className="report-columns"><div><h3>Strengths</h3>{(result.report?.strengths || []).map((x, i) => <p className="report-bullet" key={i}><CheckCircle2 size={15} />{x}</p>)}</div><div><h3>Gaps to address</h3>{(result.report?.gaps || []).map((x, i) => <p className="report-bullet" key={i}><XCircle size={15} />{x}</p>)}</div></div><h3>Suggested next steps</h3><ol className="next-steps">{(result.report?.next_steps || []).map((x, i) => <li key={i}>{x}</li>)}</ol></div></section>
        {result.keywords?.length > 0 && <section className="keyword-panel"><h3>Keywords extracted from the job</h3><div className="keyword-list">{result.keywords.map((x) => <span key={x}>{x}</span>)}</div></section>}
        <p className="scoring-note"><strong>How to read this report:</strong> {result.scoring_note} It is a decision-support estimate, not a hiring prediction.</p>
        <div className="bottom-action-row"><button className="secondary-button" onClick={() => { const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'folioport-job-fit-report.json'; a.click(); URL.revokeObjectURL(url); }}><FileText size={16} /> Export report JSON</button><button className="primary-button" onClick={reset}>Analyse another role <Plus size={16} /></button></div>
      </div>}
    </main>
    <footer className="matcher-footer"><span>folioport</span><span>Grounded in your saved portfolio · Built for clarity, not hype</span><Link to="/admin/login">Admin</Link></footer>
  </div>;
}
