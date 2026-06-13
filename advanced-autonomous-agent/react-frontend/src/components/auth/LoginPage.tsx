import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Mail, Lock, ArrowRight, Loader, Eye, EyeOff, Sparkles, Zap } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

declare global {
  interface Window {
    turnstile: any;
  }
}

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const { login, error } = useAuth();
  const [captchaToken, setCaptchaToken] = useState("");
  const [showCaptcha, setShowCaptcha] = useState(false)

  useEffect(() => {
    if (showCaptcha && window.turnstile) {

      const container = document.querySelector('.cf-turnstile')
      if (container) container.innerHTML = '';
  
      window.turnstile.render(".cf-turnstile", {
        sitekey: import.meta.env.VITE_TURNSTILE_SITE_KEY,
        theme: "dark",
  
        callback: (token: string) => {
          setCaptchaToken(token);
        },
      });
  
    }
  }, [showCaptcha]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    setIsLoading(true);

    try { 
      await login(email, password, captchaToken || undefined);

      setCaptchaToken("");
      setShowCaptcha(false);

    } catch (err: any) {

      const detail = err?.response?.data?.detail;
      if (detail === 'Captcha token required') {
        setShowCaptcha(true);
      }

    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-root">
      {/* Animated grid background */}
      <div className="auth-grid" />

      {/* Floating orbs */}
      <motion.div
        className="orb orb-1"
        animate={{ y: [0, -30, 0], x: [0, 20, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="orb orb-2"
        animate={{ y: [0, 25, 0], x: [0, -15, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
      />
      <motion.div
        className="orb orb-3"
        animate={{ y: [0, -20, 0], x: [0, 10, 0] }}
        transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
      />

      <div className="auth-container">
        {/* Left panel — branding */}
        <motion.div
          className="auth-brand"
          initial={{ opacity: 0, x: -40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
        >
          <div className="brand-content">
            <motion.div
              className="brand-logo"
              whileHover={{ scale: 1.05, rotate: 3 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              <div className="logo-glow" />
              <div className="logo-inner">
                <Brain className="logo-icon" />
              </div>
            </motion.div>

            <h1 className="brand-title">AutoAgent<br /><span className="brand-os">OS</span></h1>
            <p className="brand-sub">Autonomous Multi-Agent Intelligence Platform</p>

            <div className="brand-features">
              {[
                { icon: '⚡', text: 'Real-time agent orchestration' },
                { icon: '🎯', text: 'AI-powered job matching' },
                { icon: '📊', text: 'Personalized career reports' },
                { icon: '🔒', text: 'Enterprise-grade security' },
              ].map((f, i) => (
                <motion.div
                  key={i}
                  className="feature-pill"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.1 }}
                >
                  <span>{f.icon}</span>
                  <span>{f.text}</span>
                </motion.div>
              ))}
            </div>

            <div className="brand-stat-row">
              {[
                { value: '10K+', label: 'Jobs Matched' },
                { value: '98%', label: 'Accuracy' },
                { value: '< 2min', label: 'Report Time' },
              ].map((s, i) => (
                <motion.div
                  key={i}
                  className="brand-stat"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.6 + i * 0.1 }}
                >
                  <span className="stat-val">{s.value}</span>
                  <span className="stat-lbl">{s.label}</span>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Right panel — form */}
        <motion.div
          className="auth-form-panel"
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
        >
          <div className="form-card">
            {/* Badge */}
            <motion.div
              className="form-badge"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
              >
                <Sparkles className="badge-icon" />
              </motion.div>
              <span>AI-Powered Platform</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <h2 className="form-title">Welcome back</h2>
              <p className="form-subtitle">Sign in to your AutoAgent OS account</p>
            </motion.div>

            <form onSubmit={handleSubmit} className="auth-form">
              {/* Email */}
              <motion.div
                className="field-group"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
              >
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

              {/* Password */}
              <motion.div
                className="field-group"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
              >
                <div className="field-label-row">
                  <label className="field-label">Password</label>
                  <a href="#" className="forgot-link">Forgot password?</a>
                </div>
                <div className={`field-wrap ${focusedField === 'password' ? 'focused' : ''}`}>
                  <Lock className="field-icon" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    onFocus={() => setFocusedField('password')}
                    onBlur={() => setFocusedField(null)}
                    placeholder="••••••••"
                    className="field-input"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="eye-btn"
                  >
                    {showPassword ? <EyeOff className="eye-icon" /> : <Eye className="eye-icon" />}
                  </button>
                </div>
              </motion.div>

              {/* Error */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    className="error-box"
                    initial={{ opacity: 0, y: -8, height: 0 }}
                    animate={{ opacity: 1, y: 0, height: 'auto' }}
                    exit={{ opacity: 0, y: -8, height: 0 }}
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {showCaptcha && (
              <div className="flex justify-center mt-4">
                <div className="cf-turnstile"></div>
              </div>
              )}

              {/* Submit */}
              <motion.button
                type="submit"
                disabled={isLoading}
                className="submit-btn"
                whileHover={{ scale: 1.02, y: -2 }}
                whileTap={{ scale: 0.98 }}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
              >
                <span className="btn-glow" />
                <span className="btn-content">
                  {isLoading ? (
                    <>
                      <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}>
                        <Loader className="btn-icon" />
                      </motion.div>
                      Signing in...
                    </>
                  ) : (
                    <>
                      Sign in
                      <ArrowRight className="btn-icon" />
                    </>
                  )}
                </span>
              </motion.button>

              {/* Divider */}
              <div className="divider">
                <span className="divider-line" />
                <span className="divider-text">or</span>
                <span className="divider-line" />
              </div>

              {/* Live indicator */}
              <motion.div
                className="live-badge"
                animate={{ opacity: [0.7, 1, 0.7] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <Zap className="live-icon" />
                <span>Real-time agent monitoring active</span>
              </motion.div>
            </form>

            <motion.p
              className="switch-auth"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8 }}
            >
              Don't have an account?{' '}
              <Link to="/signup" className="switch-link">
                Create account <ArrowRight className="inline-arrow" />
              </Link>
            </motion.p>
          </div>
        </motion.div>
      </div>

      <style>{authStyles}</style>
    </div>
  );
}

const authStyles = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

  .auth-root {
    min-height: 100svh;
    width: 100%;
    background: #020408;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'DM Sans', sans-serif;
    position: relative;
    overflow-x: hidden;
    overflow-y: auto;
    padding: 20px;
  }
  .auth-grid {
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(99,179,237,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(99,179,237,0.04) 1px, transparent 1px);
    background-size: 60px 60px;
    pointer-events: none;
  }

  .orb {
    position: fixed;
    border-radius: 50%;
    filter: blur(80px);
    pointer-events: none;
    opacity: 0.15;
  }
  .orb-1 { width: 500px; height: 500px; background: #3b82f6; top: -100px; left: -100px; }
  .orb-2 { width: 400px; height: 400px; background: #8b5cf6; bottom: -80px; right: -80px; }
  .orb-3 { width: 300px; height: 300px; background: #06b6d4; top: 50%; left: 50%; transform: translate(-50%,-50%); }

  .auth-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    min-height: 100svh;
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
    position: relative;
    z-index: 1;
    min-width: 0;
  }
  @media (max-width: 900px) {
  .auth-root {
    padding: 12px;
  }

  .auth-container {
    display: block;
    width: 100%;
    max-width: 420px;
    min-height: auto;
    margin: 0 auto;
  }

  .auth-brand {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
  }

  .auth-form-panel {
    width: 100%;
    padding: 20px 0;
  }
}

  .auth-brand {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 60px 50px;
    border-right: 1px solid rgba(255,255,255,0.06);
    min-width: 0;
    overflow: hidden;
  }

  .brand-content { max-width: 400px; }

  .brand-logo {
    position: relative;
    width: 72px; height: 72px;
    margin-bottom: 32px;
    cursor: pointer;
  }
  .logo-glow {
    position: absolute;
    inset: -6px;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    border-radius: 20px;
    filter: blur(12px);
    opacity: 0.6;
  }
  .logo-inner {
    position: relative;
    width: 100%; height: 100%;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .logo-icon { width: 36px; height: 36px; color: white; }

  .brand-title {
    font-family: 'Syne', sans-serif;
    font-size: 52px;
    font-weight: 800;
    color: white;
    line-height: 1.05;
    margin-bottom: 12px;
    letter-spacing: -2px;
  }
  .brand-os {
    background: linear-gradient(135deg, #3b82f6, #8b5cf6, #06b6d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .brand-sub {
    color: rgba(255,255,255,0.45);
    font-size: 15px;
    line-height: 1.6;
    margin-bottom: 40px;
    font-weight: 300;
  }

  .brand-features { display: flex; flex-direction: column; gap: 10px; margin-bottom: 48px; }

  .feature-pill {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    color: rgba(255,255,255,0.7);
    font-size: 14px;
    font-weight: 400;
    transition: all 0.2s;
  }
  .feature-pill:hover {
    background: rgba(59,130,246,0.1);
    border-color: rgba(59,130,246,0.3);
    color: white;
  }

  .brand-stat-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
  .brand-stat {
    text-align: center;
    padding: 16px 8px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
  }
  .stat-val {
    display: block;
    font-family: 'Syne', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: white;
    margin-bottom: 4px;
  }
  .stat-lbl {
    font-size: 11px;
    color: rgba(255,255,255,0.35);
    text-transform: uppercase;
    letter-spacing: 0.8px;
  }

  /* Form panel */
  .auth-form-panel {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 40px 24px;
    min-width: 0;
  }

  .form-card {
    width: 100%;
    max-width: 420px;
    min-width: 0;
  }

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
    margin-bottom: 28px;
  }
  .badge-icon { width: 13px; height: 13px; }

  .form-title {
    font-family: 'Syne', sans-serif;
    font-size: 36px;
    font-weight: 800;
    color: white;
    letter-spacing: -1.5px;
    margin-bottom: 8px;
  }
  .form-subtitle {
    color: rgba(255,255,255,0.4);
    font-size: 15px;
    margin-bottom: 40px;
    font-weight: 300;
  }

  .auth-form { display: flex; flex-direction: column; gap: 20px; }

  .field-group { display: flex; flex-direction: column; gap: 8px; }

  .field-label {
    font-size: 13px;
    font-weight: 500;
    color: rgba(255,255,255,0.6);
    letter-spacing: 0.3px;
  }
  .field-label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .forgot-link {
    font-size: 12px;
    color: #60a5fa;
    text-decoration: none;
    transition: color 0.2s;
  }
  .forgot-link:hover { color: #93c5fd; }

  .field-wrap {
    position: relative;
    display: flex;
    align-items: center;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    transition: all 0.2s;
  }
  .field-wrap.focused {
    border-color: rgba(59,130,246,0.6);
    background: rgba(59,130,246,0.05);
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
  }
  .field-icon {
    width: 16px; height: 16px;
    color: rgba(255,255,255,0.25);
    margin-left: 14px;
    flex-shrink: 0;
  }

  .field-input {
    flex: 1;
    width: 100%;
    min-width: 0;
    padding: 14px 14px;
    background: transparent;
    border: none;
    outline: none;
    color: white;
    font-size: 14px;
    font-family: 'DM Sans', sans-serif;
  }

  .field-input::placeholder { color: rgba(255,255,255,0.2); }

  .eye-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0 14px;
    display: flex;
    align-items: center;
  }
  .eye-icon { width: 16px; height: 16px; color: rgba(255,255,255,0.3); }
  .eye-btn:hover .eye-icon { color: rgba(255,255,255,0.6); }

  .error-box {
    padding: 12px 16px;
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 10px;
    color: #f87171;
    font-size: 13px;
    overflow: hidden;
  }

  .submit-btn {
    position: relative;
    width: 100%;
    padding: 15px;
    border: none;
    border-radius: 12px;
    cursor: pointer;
    overflow: hidden;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    margin-top: 4px;
  }
  .submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .btn-glow {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    opacity: 0;
    transition: opacity 0.3s;
  }
  .submit-btn:hover:not(:disabled) .btn-glow { opacity: 1; }

  .btn-content {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: white;
    font-size: 15px;
    font-weight: 600;
    font-family: 'Syne', sans-serif;
    letter-spacing: 0.3px;
  }
  .btn-icon { width: 16px; height: 16px; }

  .divider {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .divider-line {
    flex: 1;
    height: 1px;
    background: rgba(255,255,255,0.08);
  }
  .divider-text {
    font-size: 12px;
    color: rgba(255,255,255,0.25);
    letter-spacing: 1px;
  }

  .live-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px;
    background: rgba(6,182,212,0.08);
    border: 1px solid rgba(6,182,212,0.2);
    border-radius: 10px;
    color: #22d3ee;
    font-size: 13px;
    font-weight: 400;
  }
  .live-icon { width: 14px; height: 14px; }

  .switch-auth {
    margin-top: 28px;
    text-align: center;
    color: rgba(255,255,255,0.35);
    font-size: 14px;
  }
  .switch-link {
    color: #60a5fa;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .switch-link:hover { color: #93c5fd; }
  .inline-arrow { width: 13px; height: 13px; }

  @media (max-width: 480px) {
  .auth-root {
    min-height: 100svh;
    padding: 12px;
    align-items: flex-start;
  }

  .auth-container {
    width: 100%;
    min-height: auto;
  }

  .auth-form-panel {
    width: 100%;
    padding: 28px 0;
    min-width: 0;
  }

  .form-card {
    width: 100%;
    max-width: 100%;
  }

  .form-title {
    font-size: 28px;
  }

  .form-subtitle {
    font-size: 13px;
    margin-bottom: 28px;
  }

  .field-label-row {
    flex-wrap: wrap;
    gap: 6px;
  }

  .field-input {
    font-size: 13px;
    padding: 13px 10px;
  }

  .live-badge {
    flex-wrap: wrap;
    text-align: center;
    font-size: 12px;
  }
}
`;


