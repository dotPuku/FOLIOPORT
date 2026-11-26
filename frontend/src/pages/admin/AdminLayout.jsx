import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { BriefcaseBusiness, Code2, GraduationCap, LogOut, Menu, Moon, RefreshCw, Sun, UserRound, X, Zap } from 'lucide-react';
import { api, setToken } from '../../api';
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
  const navigate = useNavigate();

  useEffect(() => {
    const onExpired = () => navigate('/admin/login', { replace: true });
    window.addEventListener('folioport:auth-expired', onExpired);
    api('/auth/me').then(setUser).catch(() => { setToken(null); navigate('/admin/login', { replace: true }); });
    return () => window.removeEventListener('folioport:auth-expired', onExpired);
  }, [navigate]);

  const logout = () => { setToken(null); navigate('/admin/login', { replace: true }); };
  const reindex = async () => {
    setReindexing(true); setNotice('');
    try { const res = await api('/admin/reindex', { method: 'POST', body: {} }); setNoticeType('success'); setNotice(`Search index updated (${res.indexed} chunks).`); }
    catch (err) { setNoticeType('error'); setNotice(err.message || 'Could not refresh the search index.'); }
    finally { setReindexing(false); }
  };

  return <div className="admin-shell">
    <aside className={`admin-sidebar ${mobileOpen ? 'admin-sidebar-open' : ''}`}>
      <div className="admin-brand-row"><Link to="/admin/profile" className="brand-lockup" onClick={() => setMobileOpen(false)}><span className="brand-mark">f.</span><span>folioport</span></Link><span className="admin-badge">ADMIN</span><button className="icon-button mobile-only" onClick={() => setMobileOpen(false)} aria-label="Close admin navigation"><X size={17} /></button></div>
      <nav className="admin-nav">{nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setMobileOpen(false)} className={({ isActive }) => `admin-nav-link ${isActive ? 'active' : ''}`}><Icon size={17} /><span>{label}</span></NavLink>)}</nav>
      <div className="admin-sidebar-spacer" />
      <div className="index-status-card"><div className="index-status-top"><span className="index-status-icon"><RefreshCw size={15} /></span><strong>Search index</strong></div><p>Refresh the Qdrant index after bulk changes or a connectivity issue.</p><button onClick={reindex} disabled={reindexing}>{reindexing ? <RefreshCw size={13} className="spin" /> : <RefreshCw size={13} />}{reindexing ? 'Refreshing…' : 'Rebuild index'}</button></div>
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
