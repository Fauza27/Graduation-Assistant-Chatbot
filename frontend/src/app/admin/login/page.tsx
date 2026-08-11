'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff } from 'lucide-react';
import { adminLogin } from '@/lib/adminAuth';

export default function AdminLogin() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  
  const [userError, setUserError] = useState(false);
  const [passError, setPassError] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    let valid = true;
    
    if (!username.trim()) {
      setUserError(true);
      valid = false;
    } else {
      setUserError(false);
    }
    
    if (!password) {
      setPassError(true);
      valid = false;
    } else {
      setPassError(false);
    }

    if (!valid) return;

    setIsSubmitting(true);
    const result = await adminLogin(username, password, rememberMe);
    if (result.success) {
      router.push('/admin/dashboard');
    } else {
      setErrorMsg(result.message || 'Login gagal.');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="admin-login-screen">
      <div className="admin-login-brand">
        <div className="admin-login-brand-blob b1"></div>
        <div className="admin-login-brand-blob b2"></div>
        <div className="admin-login-brand-content">
          <div className="admin-login-brand-logo">
            <svg className="brand-mark" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
              <circle cx="20" cy="20" r="19" fill="#F5F1FC" />
              <circle cx="20" cy="20" r="13" fill="none" stroke="#6D28D9" strokeWidth="2" />
              <circle cx="20" cy="20" r="4" fill="#6D28D9" />
            </svg>
            <div>
              <div className="b1">STMIK</div>
              <div className="b2">WIDYA CIPTA DHARMA</div>
            </div>
          </div>
          <h1>Admin Dashboard</h1>
          <div className="sub">Chatbot Asisten Virtual RAG</div>
          <p className="desc">Kelola knowledge base, chunk dokumen, dan pantau performa sistem dengan mudah.</p>
        </div>
      </div>

      <div className="admin-login-form-wrap">
        <div className="admin-login-card">
          <div className="admin-login-card-head">
            <h2>Login Admin</h2>
            <p className="body2">Masuk ke akun administrator</p>
          </div>
          <form className="admin-login-form" onSubmit={handleSubmit} noValidate>
            <div className={`field ${userError ? 'has-error' : ''}`}>
              <label htmlFor="loginUsername">Username</label>
              <input 
                className="input" 
                type="text" 
                id="loginUsername" 
                placeholder="admin" 
                autoComplete="username"
                value={username}
                onChange={e => { setUsername(e.target.value); setUserError(false); }}
              />
              <span className="field-error">Username wajib diisi.</span>
            </div>
            <div className={`field ${passError ? 'has-error' : ''}`}>
              <label htmlFor="loginPassword">Password</label>
              <div className="input-wrap">
                <input 
                  className="input" 
                  type={showPassword ? 'text' : 'password'} 
                  id="loginPassword" 
                  placeholder="••••••••" 
                  autoComplete="current-password"
                  value={password}
                  onChange={e => { setPassword(e.target.value); setPassError(false); }}
                />
                <button 
                  type="button" 
                  className="icon-btn input-icon-btn icon-btn-sm" 
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label="Tampilkan password"
                >
                  {showPassword ? <EyeOff className="icon-sm" /> : <Eye className="icon-sm" />}
                </button>
              </div>
              <span className="field-error">Password wajib diisi.</span>
            </div>
            
            {errorMsg && (
              <div style={{ color: 'var(--danger)', fontSize: '13px', textAlign: 'center' }}>
                {errorMsg}
              </div>
            )}

            <div className="admin-login-row-between">
              <div className="checkbox-row">
                <input 
                  type="checkbox" 
                  id="rememberMe" 
                  checked={rememberMe}
                  onChange={e => setRememberMe(e.target.checked)}
                />
                <label htmlFor="rememberMe">Ingat saya</label>
              </div>
            </div>
            <button type="submit" className="btn btn-primary btn-block" disabled={isSubmitting}>
              <span>{isSubmitting ? 'Memproses...' : 'Masuk'}</span>
            </button>
          </form>
          <div className="admin-login-footnote">
            <p className="caption">© 2026 STMIK Widya Cipta Dharma</p>
          </div>
        </div>
      </div>
    </div>
  );
}
