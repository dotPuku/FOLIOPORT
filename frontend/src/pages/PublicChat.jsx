import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowDown, ArrowUp, BriefcaseBusiness, CircleHelp, LoaderCircle, Menu, MessageCircle, Moon, Plus, Sun, UserRound, X, Sparkles } from 'lucide-react';
import { api, apiStream } from '../api';
import Toast, { ToastStack } from '../components/Toast';
import useScrollHeader from '../useScrollHeader';

const HISTORY_KEY = 'folioport_chat_history_v1';
const makeChat = () => ({ id: crypto.randomUUID?.() || String(Date.now()), title: 'New conversation', messages: [], updatedAt: Date.now() });
const INITIAL_RESPONSE_STATUS = 'Finding saved portfolio details…';
const suggestions = [
  { icon: UserRound, title: 'Introduce the candidate', prompt: 'Write a concise third-person professional introduction for a recruiter, based on the candidate’s portfolio.' },
  { icon: BriefcaseBusiness, title: 'Project deep dive', prompt: 'Describe the projects in detail, including their technologies, role, goals, and saved outcomes.' },
  { icon: Sparkles, title: 'Technical strengths', prompt: 'List the candidate’s skills with their saved categories, levels, experience, and details.' },
  { icon: CircleHelp, title: 'Career fit', prompt: 'Which entry-level software roles best fit the verified portfolio, and why?' },
];

export default function PublicChat({ theme, setTheme }) {
  const [chats, setChats] = useState(() => {
    try { const value = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); return Array.isArray(value) ? value : []; }
    catch { return []; }
  });
  const [activeId, setActiveId] = useState(() => chats[0]?.id || null);
  const [input, setInput] = useState('');
  const [loadingChats, setLoadingChats] = useState(() => new Set());
  const [responseStatus, setResponseStatus] = useState(INITIAL_RESPONSE_STATUS);
  const [error, setError] = useState('');
  const [profile, setProfile] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showScrollDown, setShowScrollDown] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const scrollRef = useRef(null);
  const headerVisible = useScrollHeader(scrollRef);

  const activeChat = useMemo(() => chats.find((chat) => chat.id === activeId) || null, [chats, activeId]);
  const messages = activeChat?.messages || [];
  const busy = Boolean(activeId && loadingChats.has(activeId));

  useEffect(() => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(chats.slice(0, 30)));
  }, [chats]);

  useEffect(() => {
    api('/public/portfolio').then((data) => setProfile(data.profile || {})).catch(() => setProfile({}));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: busy ? 'auto' : 'smooth', block: 'end' });
  }, [messages.length, messages[messages.length - 1]?.content?.length, busy]);

  const updateChat = (id, update) => setChats((prev) => prev.map((item) => item.id === id ? { ...item, ...update, updatedAt: Date.now() } : item));

  const newChat = () => {
    const chat = makeChat();
    setChats((prev) => [chat, ...prev]);
    setActiveId(chat.id);
    setInput(''); setError(''); setSidebarOpen(false);
    setTimeout(() => inputRef.current?.focus(), 40);
  };

  const submit = async (overrideText) => {
    const text = (overrideText ?? input).trim();
    if (!text || (activeId && loadingChats.has(activeId))) return;
    const chat = activeChat || makeChat();
    if (!activeChat) { setChats((prev) => [chat, ...prev]); setActiveId(chat.id); }
    const userMessage = { role: 'user', content: text };
    const nextMessages = [...(chat.messages || []), userMessage];
    updateChat(chat.id, { messages: nextMessages, title: (chat.messages || []).length === 0 ? text.slice(0, 42) + (text.length > 42 ? '…' : '') : chat.title });
    setInput(''); if (inputRef.current) inputRef.current.style.height = 'auto'; setLoadingChats((prev) => new Set(prev).add(chat.id)); setError('');
    setResponseStatus(INITIAL_RESPONSE_STATUS);
    let responseText = '';
    updateChat(chat.id, { messages: [...nextMessages, { role: 'assistant', content: '' }] });
    try {
      await apiStream('/chat', { messages: nextMessages.slice(-10), stream: true }, (token) => {
        responseText += token;
        updateChat(chat.id, { messages: [...nextMessages, { role: 'assistant', content: responseText }] });
      }, setResponseStatus);
    } catch (err) {
      setError(err.message || 'Unable to answer right now.');
      const failure = `I couldn't complete that response: ${err.message || 'Please try again.'}`;
      updateChat(chat.id, { messages: [...nextMessages, { role: 'assistant', content: responseText ? `${responseText}\n\n${failure}` : failure }] });
    } finally {
      setLoadingChats((prev) => { const next = new Set(prev); next.delete(chat.id); return next; });
    }
  };

  const onComposerKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(); }
  };

  const deleteChat = (event, id) => {
    event.stopPropagation();
    const next = chats.filter((chat) => chat.id !== id);
    setChats(next);
    if (activeId === id) setActiveId(next[0]?.id || null);
  };

  return (
    <div className="public-shell">
      <aside className={`public-sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand-row">
          <Link to="/" className="brand-lockup" onClick={() => setSidebarOpen(false)}>
            <span className="brand-mark">f.</span><span>folioport</span>
          </Link>
        </div>
        <button className="new-chat-button" onClick={newChat}><Plus size={17} /> New conversation</button>
        <div className="sidebar-section-label">YOUR CONVERSATIONS</div>
        <div className="chat-history-list">
          {chats.length === 0 && <p className="muted small sidebar-empty">Your recent chats will appear here.</p>}
          {chats.map((chat) => (
            <button key={chat.id} className={`history-item ${chat.id === activeId ? 'active' : ''}`} onClick={() => { setActiveId(chat.id); setSidebarOpen(false); }} title={chat.title}>
              <MessageCircle size={15} /><span>{chat.title || 'New conversation'}</span>
              {loadingChats.has(chat.id) ? <LoaderCircle className="spin" size={14} aria-label="Loading response" /> : <span role="button" tabIndex={0} className="history-delete" aria-label="Delete chat" onClick={(e) => deleteChat(e, chat.id)} onKeyDown={(e) => e.key === 'Enter' && deleteChat(e, chat.id)}><X size={13} /></span>}
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <Link className="sidebar-link" to="/jobmatcher" onClick={() => setSidebarOpen(false)}><BriefcaseBusiness size={17} /> Job matcher <span className="sidebar-link-arrow">↗</span></Link>
          <Link className="sidebar-link" to="/admin/login" onClick={() => setSidebarOpen(false)}><UserRound size={17} /> Admin sign in</Link>
          <button className="theme-row" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            <span className="theme-row-left">{theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />} Appearance</span>
            <span className="theme-pill">{theme === 'dark' ? 'Dark' : 'Light'}</span>
          </button>
        </div>
      </aside>
      {sidebarOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <main className="chat-main">
        <ToastStack><Toast message={error} type="error" onDismiss={() => setError('')} /></ToastStack>
        <header className={`chat-topbar scroll-aware-header ${headerVisible ? '' : 'scroll-aware-header-hidden'}`}>
          <div className="topbar-left">
            <button className="icon-button mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
            <div className="model-switcher">FOLIOPORT AI</div>
          </div>
          <div className="topbar-right">
            <Link className="topbar-job-link" to="/jobmatcher"><BriefcaseBusiness size={15} /> Job matcher</Link>
            <button className="icon-button desktop-hide-theme" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">{theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}</button>
          </div>
        </header>

        <section className={`chat-content ${messages.length ? 'has-messages' : 'welcome-content'}`} ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="welcome-panel">
              <div className="welcome-symbol">f.</div>
              <p className="eyebrow">PERSONAL PORTFOLIO ASSISTANT</p>
              <h1>{profile?.full_name ? `Ask me about ${profile.full_name.split(' ')[0]}.` : 'What would you like to know?'}</h1>
              <p className="welcome-copy">Ask about projects, technical skills, education, experience, or role fit. Answers are grounded in the portfolio records.</p>
              <div className="suggestion-grid">
                {suggestions.map(({ icon: Icon, title, prompt }) => <button className="suggestion-card" key={title} onClick={() => submit(prompt)}><Icon size={18} /><span>{title}</span><small>{prompt}</small></button>)}
              </div>
            </div>
          ) : (
            <div className="message-thread">
              {messages.map((message, index) => {
                if (message.role === 'assistant' && !message.content) return null;
                return (
                  <article key={`${activeId}-${index}`} className={`message-row ${message.role}`}>
                    {message.role === 'assistant' && <div className="assistant-avatar">f.</div>}
                    <div className="message-body">
                      {message.role === 'user' ? <p className="user-message-text">{message.content}</p> : <div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown></div>}
                    </div>
                  </article>
                );
              })}
              {busy && !messages[messages.length - 1]?.content && <article className="message-row assistant"><div className="assistant-avatar">f.</div><div className="message-body typing-state"><span /><span /><span /><small>{responseStatus}</small></div></article>}
              <div ref={bottomRef} />
            </div>
          )}
        </section>

        <footer className="composer-dock">
          <form className="composer-box" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <textarea ref={inputRef} value={input} rows={1} placeholder="Ask anything about this portfolio…" aria-label="Message FOLIOPORT AI" onChange={(e) => { setInput(e.target.value); e.target.style.height = 'auto'; e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`; }} onKeyDown={onComposerKeyDown} maxLength={5000} />
            <div className="composer-actions">
              <span className="composer-hint"><span className="keyboard-key">↵</span> to send · Shift + ↵ for new line</span>
              <button className="send-button" type="submit" disabled={!input.trim() || busy} aria-label="Send message">{busy ? <span className="button-spinner" /> : <ArrowUp size={18} />}</button>
            </div>
          </form>
          <p className="composer-disclaimer">FOLIOPORT AI can make mistakes. Verify important details against the original portfolio records.</p>
        </footer>
      </main>
    </div>
  );
}
