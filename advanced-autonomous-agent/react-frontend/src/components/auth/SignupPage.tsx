import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Mail, Lock, ArrowRight, Loader, Eye, EyeOff,
  Sparkles, User, CheckCircle, Shield
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

const PasswordStrength = ({ password }: { password: string }) => {
  const checks = [
    { label: 'At least 8 characters', ok: password.length >= 8 },
    { label: 'One uppercase letter', ok: /[A-Z]/.test(password) },
    { label: 'One number', ok: /\d/.test(password) },
    { label: 'One special character', ok: /[^A-Za-z0-9]/.test(password) },
  ];
  const score = checks.filter(c => c.ok).length;
  const colors = ['#ef4444', '#f97316', '#eab308', '#22c55e'];
  const labels = ['Weak', 'Fair', 'Good', 'Strong'];

  if (!password) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="strength-wrap"
    >
      <div className="strength-bars">
        {[0, 1, 2, 3].map(i => (
          <motion.div
            key={i}
            className="strength-bar"
            animate={{ backgroundColor: i < score ? colors[score - 1] : 'rgba(255,255,255,0.08)' }}
            transition={{ duration: 0.3 }}
          />
        ))}
      </div>
      <span className="strength-label" style={{ color: score > 0 ? colors[score - 1] : 'transparent' }}>
        {labels[score - 1] || ''}
      </span>
      <div className="strength-checks">
        {checks.map((c, i) => (
          <motion.div key={i} className="strength-check" animate={{ opacity: c.ok ? 1 : 0.4 }}>
            <CheckCircle className="check-icon" style={{ color: c.ok ? '#22c55e' : 'rgba(255,255,255,0.2)' }} />
            <span style={{ color: c.ok ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.3)' }}>{c.label}</span>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
};

export default function SignupPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [agreed, setAgreed] = useState(false);
  const { signup, error } = useAuth();

  const passwordsMatch = confirmPassword.length > 0 && password === confirmPassword;
  const passwordMismatch = confirmPassword.length > 0 && password !== confirmPassword;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword || !agreed) return;
    setIsLoading(true);
    await signup(email, password, name);
    setIsLoading(false);
  };

  return (
    <div className="auth-root">
      <div className="auth-grid" />
      <motion.div className="orb orb-1" animate={{ y: [0,-30,0], x:[0,20,0] }} transition={{ duration:8, repeat:Infinity, ease:'easeInOut' }} />
      <motion.div className="orb orb-2" animate={{ y:[0,25,0], x:[0,-15,0] }} transition={{ duration:10, repeat:Infinity, ease:'easeInOut', delay:1 }} />
      <motion.div className="orb orb-3" animate={{ y:[0,-20,0], x:[0,10,0] }} transition={{ duration:7, repeat:Infinity, ease:'easeInOut', delay:2 }} />

      <div className="auth-container">
        <motion.div
          className="auth-form-panel"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        >
          <div className="form-card">
            <motion.div className="form-badge" initial={{ opacity:0, y:-10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.15 }}>
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}>
                <Sparkles className="badge-icon" />
              </motion.div>
              <span>Join AutoAgent OS</span>
            </motion.div>

            <motion.div initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.2 }}>
              <h2 className="form-title">Create account</h2>
              <p className="form-subtitle">Start your AI-powered career journey today</p>
            </motion.div>

            <form onSubmit={handleSubmit} className="auth-form">
              <div className="field-row">
                <motion.div className="field-group" initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.3 }}>
                  <label className="field-label">Full name</label>
                  <div className={`field-wrap ${focusedField === 'name' ? 'focused' : ''}`}>
                    <User className="field-icon" />
                    <input
                      type="text"
                      value={name}
                      onChange={e => setName(e.target.value)}
                      onFocus={() => setFocusedField('name')}
                      onBlur={() => setFocusedField(null)}
                      placeholder="John Doe"
                      className="field-input"
                      required
                    />
                  </div>
                </motion.div>

                <motion.div className="field-group" initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.35 }}>
                  <label className="field-label">Email address</label>
                  <div className={`field-wrap ${focusedField === 'email' ? 'focused' : ''}`}>
                    <Mail className="field-icon" />
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      onFocus={() => setFocusedField('email')}
                      onBlur={() => setFocusedField(null)}
                      placeholder="you@example.com"
                      className="field-input"
                      required
                    />
                  </div>
                </motion.div>
              </div>

              <motion.div className="field-group" initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.4 }}>
                <label className="field-label">Password</label>
                <div className={`field-wrap ${focusedField === 'password' ? 'focused' : ''}`}>
                  <Lock className="field-icon" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    onFocus={() => setFocusedField('password')}
                    onBlur={() => setFocusedField(null)}
                    placeholder="Create a strong password"
                    className="field-input"
                    required
                  />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="eye-btn">
                    {showPassword ? <EyeOff className="eye-icon" /> : <Eye className="eye-icon" />}
                  </button>
                </div>
                <AnimatePresence>
                  {focusedField === 'password' && <PasswordStrength password={password} />}
                </AnimatePresence>
              </motion.div>

              <motion.div className="field-group" initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.45 }}>
                <label className="field-label">Confirm password</label>
                <div className={`field-wrap ${focusedField === 'confirm' ? 'focused' : ''} ${passwordMismatch ? 'error-field' : ''} ${passwordsMatch ? 'success-field' : ''}`}>
                  <Lock className="field-icon" />
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    onFocus={() => setFocusedField('confirm')}
                    onBlur={() => setFocusedField(null)}
                    placeholder="Repeat your password"
                    className="field-input"
                    required
                  />
                  <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="eye-btn">
                    {showConfirm ? <EyeOff className="eye-icon" /> : <Eye className="eye-icon" />}
                  </button>
                  {passwordsMatch && <CheckCircle className="match-icon" />}
                </div>
                <AnimatePresence>
                  {passwordMismatch && (
                    <motion.p className="mismatch-text" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}>
                      Passwords don't match
                    </motion.p>
                  )}
                </AnimatePresence>
              </motion.div>

              <motion.label className="terms-row" initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.5 }}>
                <div className={`checkbox ${agreed ? 'checked' : ''}`} onClick={() => setAgreed(!agreed)}>
                  {agreed && <CheckCircle className="checkbox-icon" />}
                </div>
                <span className="terms-text">
                  I agree to the <a href="#" className="terms-link">Terms of Service</a> and <a href="#" className="terms-link">Privacy Policy</a>
                </span>
              </motion.label>

              <AnimatePresence>
                {error && (
                  <motion.div className="error-box" initial={{ opacity:0, height:0 }} animate={{ opacity:1, height:'auto' }} exit={{ opacity:0, height:0 }}>
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              <motion.button
                type="submit"
                disabled={isLoading || !agreed || passwordMismatch}
                className="submit-btn"
                whileHover={{ scale: 1.02, y: -2 }}
                whileTap={{ scale: 0.98 }}
                initial={{ opacity:0, y:10 }}
                animate={{ opacity:1, y:0 }}
                transition={{ delay:0.55 }}
              >
                <span className="btn-glow" />
                <span className="btn-content">
                  {isLoading ? (
                    <>
                      <motion.div animate={{ rotate: 360 }} transition={{ duration:1, repeat:Infinity, ease:'linear' }}>
                        <Loader className="btn-icon" />
                      </motion.div>
                      Creating account...
                    </>
                  ) : (
                    <>
                      <Shield className="btn-icon" />
                      Create secure account
                      <ArrowRight className="btn-icon" />
                    </>
                  )}
                </span>
              </motion.button>

              <motion.div className="trust-row" initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ delay:0.65 }}>
                {['256-bit encryption', 'No spam ever', 'Cancel anytime'].map((t, i) => (
                  <div key={i} className="trust-item">
                    <CheckCircle className="trust-icon" />
                    <span>{t}</span>
                  </div>
                ))}
              </motion.div>
            </form>

            <motion.p className="switch-auth" initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ delay:0.7 }}>
              Already have an account?{' '}
              <Link to="/login" className="switch-link">
                Sign in <ArrowRight className="inline-arrow" />
              </Link>
            </motion.p>
          </div>
        </motion.div>
      </div>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

   *, *::before, *::after {
    box-sizing: border-box;
  }

  .auth-root {
    min-height: 100dvh;
    width: 100%;
    background: #020408;
    display: block !important;
    font-family: 'DM Sans', sans-serif;
    position: relative;
    overflow-x: hidden;
    overflow-y: auto;
    padding: 8px;
  }

  .auth-grid {
    position: fixed; inset: 0;
    background-image:
      linear-gradient(rgba(99,179,237,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(99,179,237,0.04) 1px, transparent 1px);
    background-size: 60px 60px;
    pointer-events: none;
  }

  .orb { position: fixed; border-radius: 50%; filter: blur(80px); pointer-events: none; opacity: 0.15; }
  .orb-1 { width: 500px; height: 500px; background: #3b82f6; top: -100px; left: -100px; }
  .orb-2 { width: 400px; height: 400px; background: #8b5cf6; bottom: -80px; right: -80px; }
  .orb-3 { width: 300px; height: 300px; background: #06b6d4; top: 50%; left: 50%; transform: translate(-50%,-50%); }

  .auth-container {
    width: 100%;
    max-width: 420px;
    margin: 0 auto;
    position: relative;
    z-index: 1;
    box-sizing: border-box;
    min-width: 0;
  }

  .auth-form-panel {
    width: 100%;
    padding: 8px 0;
  }

  .form-card {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    box-sizing: border-box;
  }

  /* Badge */
  .form-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    background: rgba(59,130,246,0.1);
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: 100px;
    color: #60a5fa;
    font-size: 12px;
    font-weight: 500;
    margin-bottom: 20px;
  }
  .badge-icon { width: 13px; height: 13px; }

  .form-title {
    font-family: 'Syne', sans-serif;
    font-size: 32px;
    font-weight: 800;
    color: white;
    letter-spacing: -1.5px;
    margin-bottom: 8px;
  }
  .form-subtitle {
    color: rgba(255,255,255,0.4);
    font-size: 14px;
    margin-bottom: 28px;
    font-weight: 300;
  }

  /* Form */
  .auth-form { display: flex; flex-direction: column; gap: 16px; }
  .field-group { display: flex; flex-direction: column; gap: 8px; }
  .field-label { font-size: 13px; font-weight: 500; color: rgba(255,255,255,0.6); letter-spacing: 0.3px; }

  /* Two-col row — stacks on mobile */
  .field-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .field-wrap {
    position: relative;
    display: flex;
    align-items: center;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    transition: all 0.2s;
    box-sizing: border-box;
    width: 100%;
    overflow: hidden;
  }
  
  .field-group,
  .field-wrap,
  .field-input,
  .auth-form {
    min-width: 0;
  }
    
  .field-wrap.focused {
    border-color: rgba(59,130,246,0.6);
    background: rgba(59,130,246,0.05);
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
  }
  .error-field { border-color: rgba(239,68,68,0.5) !important; background: rgba(239,68,68,0.05) !important; }
  .success-field { border-color: rgba(34,197,94,0.5) !important; background: rgba(34,197,94,0.05) !important; }

  .field-icon { width: 16px; height: 16px; color: rgba(255,255,255,0.25); margin-left: 14px; flex-shrink: 0; }

  .field-input {
    flex: 1;
    min-width: 0;
    padding: 13px 12px;
    background: transparent !important;
    border: none;
    outline: none;
    color: white !important;
    font-size: 16px; /* 16px prevents iOS auto-zoom */
    font-family: 'DM Sans', sans-serif;
  }
  .field-input::placeholder { color: rgba(255,255,255,0.2); }

  .eye-btn { background: none; border: none; cursor: pointer; padding: 0 14px; display: flex; align-items: center; flex-shrink: 0; }
  .eye-icon { width: 16px; height: 16px; color: rgba(255,255,255,0.3); }

  .match-icon { width: 16px; height: 16px; color: #22c55e; margin-right: 12px; flex-shrink: 0; }
  .mismatch-text { font-size: 12px; color: #f87171; margin-top: 4px; }

  /* Password strength */
  .strength-wrap { margin-top: 10px; overflow: hidden; }
  .strength-bars { display: flex; gap: 4px; margin-bottom: 6px; }
  .strength-bar { flex: 1; height: 3px; border-radius: 2px; background: rgba(255,255,255,0.08); }
  .strength-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; display: block; }
  .strength-checks { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; }
  .strength-check { display: flex; align-items: center; gap: 6px; font-size: 11px; }
  .check-icon { width: 12px; height: 12px; flex-shrink: 0; }

  /* Terms */
  .terms-row { display: flex; align-items: flex-start; gap: 12px; cursor: pointer; }
  .checkbox {
    width: 20px; height: 20px;
    border: 1.5px solid rgba(255,255,255,0.2);
    border-radius: 6px;
    flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.2s;
    margin-top: 1px;
    background: rgba(255,255,255,0.03);
  }
  .checkbox.checked { border-color: #3b82f6; background: rgba(59,130,246,0.2); }
  .checkbox-icon { width: 13px; height: 13px; color: #60a5fa; }
  .terms-text { font-size: 13px; color: rgba(255,255,255,0.45); line-height: 1.5; }
  .terms-link { color: #60a5fa; text-decoration: none; }
  .terms-link:hover { color: #93c5fd; }

  /* Error */
  .error-box { padding: 12px 16px; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); border-radius: 10px; color: #f87171; font-size: 13px; overflow: hidden; }

  /* Submit */
  .submit-btn {
    position: relative; width: 100%; padding: 14px;
    border: none; border-radius: 12px; cursor: pointer;
    overflow: hidden; background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  }
  .submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-glow { position: absolute; inset: 0; background: linear-gradient(135deg, #60a5fa, #a78bfa); opacity: 0; transition: opacity 0.3s; }
  .submit-btn:hover:not(:disabled) .btn-glow { opacity: 1; }
  .btn-content {
    position: relative; z-index: 1;
    display: flex; align-items: center; justify-content: center;
    gap: 8px; color: white; font-size: 15px;
    font-weight: 600; font-family: 'Syne', sans-serif; letter-spacing: 0.3px;
  }
  .btn-icon { width: 16px; height: 16px; }

  /* Trust row */
  .trust-row { display: flex; align-items: center; justify-content: center; gap: 16px; flex-wrap: wrap; }
  .trust-item { display: flex; align-items: center; gap: 5px; font-size: 11px; color: rgba(255,255,255,0.25); }
  .trust-icon { width: 11px; height: 11px; color: rgba(255,255,255,0.2); }

  /* Sign in link */
  .switch-auth { margin-top: 24px; text-align: center; color: rgba(255,255,255,0.35); font-size: 14px; }
  .switch-link { color: #60a5fa; text-decoration: none; font-weight: 500; transition: color 0.2s; display: inline-flex; align-items: center; gap: 4px; }
  .switch-link:hover { color: #93c5fd; }
  .inline-arrow { width: 13px; height: 13px; }

  /* ── Mobile ── */
  @media (max-width: 600px) {
    .field-row {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 480px) {
    .auth-root {
      padding: 16px 12px;
    }
    .form-title {
      font-size: 26px;
      letter-spacing: -1px;
    }
    .form-subtitle {
      font-size: 13px;
      margin-bottom: 20px;
    }
    .auth-form {
      gap: 14px;
    }
    .strength-checks {
      grid-template-columns: 1fr;
    }
    .trust-row {
      display: none;
    }
    .btn-content {
      font-size: 14px;
    }
    .switch-auth {
      margin-top: 18px;
      font-size: 13px;
    }
  }
`;
