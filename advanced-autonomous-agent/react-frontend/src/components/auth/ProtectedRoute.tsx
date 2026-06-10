import { Navigate } from "react-router-dom";
import { useEffect, useState } from "react";

const BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function ProtectedRoute({ children }) {
  const [loading, setLoading] = useState(true);
  const [isAuth, setIsAuth] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem("auth_token");

      if (!token) {
        setIsAuth(false);
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(`${BASE}/auth/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (res.status === 401) {
          localStorage.removeItem("auth_token");
          setIsAuth(false);
        } else {
          setIsAuth(res.ok);
        }

        setIsAuth(res.ok);
      } catch {
        setIsAuth(false);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, []);

  if (loading) {
    return <div>Loading...</div>; 
  }

  if (!isAuth) {
    return <Navigate to="/login" replace />;
  }

  return children;
}