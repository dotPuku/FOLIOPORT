import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, KeyRound, Moon, ShieldCheck, Sun } from 'lucide-react';
import { api, getToken, setToken } from '../api';
import Toast, { ToastStack } from '../components/Toast';

export default function AdminLogin({ theme, setTheme }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    if (getToken()) navigate('/admin/profile', { replace: true });
  }, [navigate]);

  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const result = await api('/auth/login', { method: 'POST', body: { username, password } });
      setToken(result.access_token);
      navigate('/admin/profile', { replace: true });
    } catch (err) { setError(err.message || 'Sign-in failed.'); }
    finally { setBusy(false); }
  };

  if (getToken()) return null;

  return <div className="login-page">
    <header className="login-topbar"><Link to="/" className="brand-lockup"><span className="brand-mark">f.</span><span>folioport</span></Link><button className="icon-button" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">{theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}</button></header>
    <main className="login-content"><div className="login-card">
      <div className="login-icon"><ShieldCheck size={22} /></div><p className="eyebrow">PRIVATE WORKSPACE</p><h1>Welcome back.</h1><p className="login-copy">Sign in to manage your profile, skills, education, projects, and experience.</p>
      <form onSubmit={submit} className="stack-form"><label className="field-label" htmlFor="admin-username">Username or email</label><input autoComplete="username" id="admin-username" value={username} onChange={(e) => setUsername(e.target.value)} required placeholder="you@example.com" /><label className="field-label" htmlFor="admin-password">Password</label><input autoComplete="current-password" id="admin-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="Your admin password" />
        <ToastStack><Toast message={error} type="error" onDismiss={() => setError('')} /></ToastStack><button className="primary-button login-submit" disabled={busy}>{busy ? 'Signing in…' : <><KeyRound size={16} /> Sign in securely</>}</button>
      </form><div className="login-security-note"><ShieldCheck size={15} /><span>Admin routes are JWT-protected. There is no public admin registration.</span></div>
      <Link className="back-link" to="/"><ArrowLeft size={14} /> Return to public portfolio</Link>
    </div><p className="login-footnote">First setup? Run <code>python -m scripts.create_admin</code> in the backend folder.</p></main>
  </div>;
}
