
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const BASE = import.meta.env.VITE_BACKEND_URL || '/api';

export function useAuth() {
  const navigate = useNavigate();
  const [error, setError] = useState('');

  const login = async (email: string, password: string, captchaToken?: string) => {
    setError('');
    try {
      const res = await fetch(`${BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          ...(captchaToken ? { captcha_token: captchaToken } : {}),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Login failed');
        throw {response: {data}};
      }

      localStorage.setItem('auth_token', data.token);
      localStorage.setItem('user_id', data.user_id);
      localStorage.setItem('user_name', data.name || '');
      navigate('/');
    } catch (err: any){
      if (err?.response) throw err;
      setError('Network error. Please try again.');
      throw err;
    }
  };

  const signup = async (email: string, password: string, name: string) => {
    setError('');
    try {
      const res = await fetch(`${BASE}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Signup failed');
        return;
      }
      navigate('/login');
    } catch {
      setError('Network error. Please try again.');
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_name');
    navigate('/login');
  };

  const getToken = () => localStorage.getItem('auth_token');
  const getUserId = () => localStorage.getItem('user_id');
  const getUserName = () => localStorage.getItem('user_name');
  const isAuthenticated = () => !!localStorage.getItem('auth_token');

  return { login, signup, logout, error, getToken, getUserId, getUserName, isAuthenticated };
}