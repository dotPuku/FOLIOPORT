import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { BriefcaseBusiness, Code2, GraduationCap, LogOut, Menu, Moon, RefreshCw, Sun, UserRound, X, Zap } from 'lucide-react';
import { api, clearAuth, setCsrfToken } from '../../api';
import Toast, { ToastStack } from '../../components/Toast';

const nav = [
  { to: '/admin/profile', label: 'Profile', icon: UserRound },
  { to: '/admin/skills', label: 'Skills', icon: Zap },
  { to: '/admin/education', label: 'Education', icon: GraduationCap },
  { to: '/admin/projects', label: 'Projects', icon: Code2 },
  { to: '/admin/experience', label: 'Experience', icon: BriefcaseBusiness },
];

export default function AdminLayout({ theme, setTheme }) {
  const [user, setUser] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notice, setNotice] = useState('');
  const [noticeType, setNoticeType] = useState('success');
  const [reindexing, setReindexing] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const [authError, setAuthError] = useState('');
  const processingJob = useRef(false);
  const navigate = useNavigate();

  const processReindexJob = useCallback(async (jobId) => {
    if (processingJob.current) return;
    processingJob.current = true;
    setReindexing(true);
    setNotice('');
    try {
      let job;
      do {
        const result = await api(`/admin/reindex/jobs/${jobId}/process`, {
          method: 'POST',
          body: {},
        });
        job = result.job;
        if (job.status === 'completed') {
          setNoticeType('success');
          setNotice(`Search index rebuilt (${job.indexed_chunks} chunks across ${job.processed_entities} records).`);
          break;
        }
        setNoticeType('success');
        setNotice(`Rebuilding search index: ${job.processed_entities}/${job.total_entities} records.`);
        if (job.status === 'running' || job.status === 'queued') {
          await new Promise((resolve) => window.setTimeout(resolve, 2100));
        }
      } while (job.status === 'running' || job.status === 'queued');
    } catch (err) {
      setNoticeType('error');
      setNotice(err.message || 'Could not refresh the search index.');
    } finally {
      processingJob.current = false;
      setReindexing(false);
    }
  }, []);

  useEffect(() => {
    const onExpired = () => {
      clearAuth();
      navigate('/admin/login', { replace: true });
    };
    window.addEventListener('folioport:auth-expired', onExpired);
    const checkSession = async () => {
      try {
        const currentUser = await api('/auth/me');
        const csrf = await api('/auth/csrf');
        setCsrfToken(csrf.csrf_token);
        setUser(currentUser);
      } catch (err) {
        clearAuth();
        if (err.status === 401) navigate('/admin/login', { replace: true });
        else setAuthError(`Could not verify the admin session: ${err.message}`);
      } finally {
        setAuthChecking(false);
      }
    };
    checkSession();
    return () => window.removeEventListener('folioport:auth-expired', onExpired);
  }, [navigate]);

  useEffect(() => {
    if (!user) return undefined;
    let active = true;
    const resumeActiveJob = async () => {
      try {
        const result = await api('/admin/reindex/jobs/active');
        if (active && result.job) await processReindexJob(result.job.id);
      } catch (err) {
        if (active) {
          setNoticeType('error');
          setNotice(`Could not check for a pending search index job: ${err.message}`);
        }
      }
    };
    const onReindexJob = (event) => {
      const jobId = event.detail?.id;
      if (active && typeof jobId === 'string') processReindexJob(jobId);
    };
    window.addEventListener('folioport:reindex-job', onReindexJob);
    resumeActiveJob();
    return () => {
      active = false;
      window.removeEventListener('folioport:reindex-job', onReindexJob);
    };
  }, [user, processReindexJob]);

  const logout = async () => {
    try {
      await api('/auth/logout', { method: 'POST', body: {} });
      clearAuth();
      navigate('/admin/login', { replace: true });
    } catch (err) {
      setNoticeType('error');
      setNotice(err.message || 'Could not sign out. Please try again.');
    }
  };
  const reindex = async () => {
    setReindexing(true); setNotice('');
    try {
      const result = await api('/admin/reindex', { method: 'POST', body: {} });
      setNoticeType('success');
      setNotice(result.message);
      processReindexJob(result.job.id);
    }
    catch (err) { setNoticeType('error'); setNotice(err.message || 'Could not refresh the search index.'); }
    finally {
      if (!processingJob.current) setReindexing(false);
    }
  };

  if (authChecking) return <div className="admin-loading" role="status">Checking admin session…</div>;
  if (authError) return <div className="admin-loading" role="alert">{authError}</div>;
  if (!user) return null;

  return <div className="admin-shell">
    <aside className={`admin-sidebar ${mobileOpen ? 'admin-sidebar-open' : ''}`}>
      <div className="admin-brand-row"><Link to="/admin/profile" className="brand-lockup" onClick={() => setMobileOpen(false)}><span className="brand-mark">f.</span><span>folioport</span></Link><span className="admin-badge">ADMIN</span><button className="icon-button mobile-only" onClick={() => setMobileOpen(false)} aria-label="Close admin navigation"><X size={17} /></button></div>
      <nav className="admin-nav">{nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setMobileOpen(false)} className={({ isActive }) => `admin-nav-link ${isActive ? 'active' : ''}`}><Icon size={17} /><span>{label}</span></NavLink>)}</nav>
      <div className="admin-sidebar-spacer" />
      <div className="index-status-card"><div className="index-status-top"><span className="index-status-icon"><RefreshCw size={15} /></span><strong>Search index</strong></div><p>Rebuilds Qdrant in five-record API batches and can resume after this page reloads.</p><button onClick={reindex} disabled={reindexing}>{reindexing ? <RefreshCw size={13} className="spin" /> : <RefreshCw size={13} />}{reindexing ? 'Refreshing…' : 'Rebuild index'}</button></div>
      <button className="theme-row admin-theme" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}><span className="theme-row-left">{theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />} Appearance</span><span className="theme-pill">{theme === 'dark' ? 'Dark' : 'Light'}</span></button>
      <div className="admin-user-row"><div className="admin-user-avatar">{(user?.username || 'A').slice(0, 1).toUpperCase()}</div><div className="admin-user-copy"><strong>{user?.username || 'Admin account'}</strong><small>{user?.email || 'Secure workspace'}</small></div><button className="icon-button" onClick={logout} title="Sign out" aria-label="Sign out"><LogOut size={16} /></button></div>
    </aside>
    {mobileOpen && <button className="sidebar-scrim" aria-label="Close admin navigation" onClick={() => setMobileOpen(false)} />}
    <main className="admin-main">
      <header className="admin-topbar"><div className="admin-topbar-left"><button className="icon-button mobile-only" onClick={() => setMobileOpen(true)} aria-label="Open admin navigation"><Menu size={19} /></button><span className="admin-breadcrumb">PORTFOLIO CONTENT</span></div><div className="admin-topbar-right"><Link className="view-public-link" to="/" target="_blank">View public site ↗</Link></div></header>
      <ToastStack><Toast message={notice} type={noticeType} onDismiss={() => setNotice('')} /></ToastStack>
      <div className="admin-page-content"><Outlet /></div>
      <footer className="admin-footer"><span>Folioport Admin</span><span>Changes save to the portfolio database</span></footer>
    </main>
  </div>;
}
