import { useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import PublicChat from './pages/PublicChat';
import JobMatcher from './pages/JobMatcher';
import AdminLogin from './pages/AdminLogin';
import AdminLayout from './pages/admin/AdminLayout';
import ProfilePage from './pages/admin/ProfilePage';
import RecordManager from './pages/admin/RecordManager';
import { getToken } from './api';

const adminSchemas = {
  skills: {
    title: 'Skills', subtitle: 'Keep your skill inventory factual, searchable, and backed by evidence.', endpoint: '/admin/skills',
    singular: 'skill', required: ['name', 'category'],
    fields: [
      { name: 'name', label: 'Skill name', required: true, placeholder: 'React, Python, SQL…' },
      { name: 'category', label: 'Type / category', type: 'category', required: true, placeholder: 'Frontend, Backend, Core Concepts…' },
      { name: 'level', label: 'Proficiency level', type: 'select', options: ['Beginner', 'Intermediate', 'Advanced'] },
      { name: 'years_experience', label: 'Years of experience', type: 'number', min: 0, step: 0.5, placeholder: 'e.g. 2.5' },
      { name: 'evidence', label: 'Evidence of experience', type: 'textarea', rows: 3, placeholder: 'Where and how did you use this skill?' },
    ],
    summary: (x) => `${x.category || 'Other'} · ${x.level || 'Level not set'} · ${Number(x.years_experience || 0)} year(s)`,
  },
  education: {
    title: 'Education', subtitle: 'Add college, degree, academic years, grades, and useful context.', endpoint: '/admin/education', singular: 'education record', required: ['institution'],
    fields: [
      { name: 'institution', label: 'School / college name', required: true, placeholder: 'Institution name' },
      { name: 'degree', label: 'Degree / qualification', placeholder: 'B.Tech' },
      { name: 'stream', label: 'Stream / specialization', placeholder: 'Computer Science, Commerce, Biology…' },
      { name: 'start_year', label: 'Start year', type: 'number', min: 1900, max: 2200, placeholder: 'e.g. 2020' },
      { name: 'is_current', label: 'Currently studying here', type: 'checkbox' },
      { name: 'end_year', label: 'End / expected year', type: 'number', min: 1900, max: 2200, placeholder: 'e.g. 2024', hideWhenCurrent: true },
      { name: 'grade_type', label: 'Grade format', type: 'select', options: ['CGPA', 'Percentage', 'Grade', 'Other'] },
      { name: 'grade_value', label: 'Grade / CGPA / percentage', placeholder: 'e.g. 7.2/10, 85%, A' },
      { name: 'location', label: 'Location', placeholder: 'City, State, Country' },
      { name: 'description', label: 'Relevant coursework / details', type: 'textarea', rows: 3, placeholder: 'Relevant courses, projects, honors, or academic details' },
    ],
    summary: (x) => `${x.degree || 'Qualification not set'} · ${x.stream || 'Stream not set'} · ${x.start_year || '—'}–${x.is_current ? 'Present' : (x.end_year || '—')}`,
  },
  projects: {
    title: 'Projects', subtitle: 'Record projects, technology stacks, outcomes, and links for RAG and job matching.', endpoint: '/admin/projects', singular: 'project', required: ['name'],
    fields: [
      { name: 'name', label: 'Project name', required: true, placeholder: 'e.g. Portfolio Website' },
      { name: 'description', label: 'Description', type: 'textarea', rows: 4, required: true, placeholder: 'What does the project do? Describe your approach and results.' },
      { name: 'tech_stack', label: 'Tech stack', type: 'list', placeholder: 'React, Flask, TiDB (comma separated)' },
      { name: 'role', label: 'Your role', placeholder: 'e.g. Full-stack developer' },
      { name: 'custom_fields', label: 'Custom key/value fields', type: 'customFields' },
      { name: 'live_url', label: 'Live URL', type: 'url', placeholder: 'https://your-project.example' },
      { name: 'github_url', label: 'GitHub URL', type: 'url', placeholder: 'https://github.com/username/project' },
    ],
    summary: (x) => `${x.role || 'Role not set'} · ${(x.tech_stack || []).join(', ') || 'Tech stack not set'}`,
  },
  experience: {
    title: 'Experience', subtitle: 'Capture internships, employment, freelance work, and practical experience.', endpoint: '/admin/experience', singular: 'experience record', required: ['company', 'title'],
    fields: [
      { name: 'company', label: 'Company / organization', required: true, placeholder: 'Company or organization name' },
      { name: 'title', label: 'Job title', required: true, placeholder: 'e.g. Software Engineer Intern' },
      { name: 'employment_type', label: 'Employment type', type: 'select', options: ['Internship', 'Full-time', 'Part-time', 'Contract', 'Freelance', 'Volunteer', 'Training'] },
      { name: 'location', label: 'Location', placeholder: 'City, State, Country' },
      { name: 'work_mode', label: 'Work mode', type: 'select', options: ['On-site', 'Hybrid', 'Remote', ''] },
      { name: 'start_date', label: 'Start date', placeholder: 'MM/YYYY or DD/MM/YYYY' },
      { name: 'is_current', label: 'Currently working here', type: 'checkbox' },
      { name: 'end_date', label: 'End date', placeholder: 'MM/YYYY or DD/MM/YYYY', hideWhenCurrent: true },
      { name: 'description', label: 'Responsibilities / overview', type: 'textarea', rows: 4, placeholder: 'Summarize your responsibilities, contributions, and impact.' },
      { name: 'achievements', label: 'Achievements / impact', type: 'list', placeholder: 'One achievement per line or comma separated' },
      { name: 'tech_stack', label: 'Tools / technology', type: 'list', placeholder: 'Python, SQL, Git' },
    ],
    summary: (x) => `${x.title || 'Role'} · ${x.employment_type || 'Experience'} · ${x.start_date || '—'}–${x.is_current ? 'Present' : (x.end_date || '—')}`,
  },
};

function Protected({ children }) {
  return getToken() ? children : <Navigate to="/admin/login" replace />;
}

function ThemeRoot({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem('folioport_theme') || 'light');
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.classList.toggle('darkMode', theme === 'dark');
    localStorage.setItem('folioport_theme', theme);
  }, [theme]);
  return children({ theme, setTheme });
}

export default function App() {
  const location = useLocation();
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }); }, [location.pathname]);
  return (
    <ThemeRoot>{({ theme, setTheme }) => (
      <Routes>
        <Route path="/" element={<PublicChat theme={theme} setTheme={setTheme} />} />
        <Route path="/jobmatcher" element={<JobMatcher theme={theme} setTheme={setTheme} />} />
        <Route path="/admin/login" element={<AdminLogin theme={theme} setTheme={setTheme} />} />
        <Route path="/admin" element={<Protected><AdminLayout theme={theme} setTheme={setTheme} /></Protected>}>
          <Route index element={<Navigate to="profile" replace />} />
          <Route path="profile" element={<ProfilePage />} />
          {Object.entries(adminSchemas).map(([key, schema]) => <Route key={key} path={key} element={<RecordManager schema={schema} />} />)}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    )}</ThemeRoot>
  );
}
