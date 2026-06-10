import { createContext, useContext, useEffect, useState } from "react";
import { useAuth as useAuthHook } from "@/hooks/useAuth"

const AuthContext = createContext<{user: any, loading: boolean}>({
    user: null,
    loading: true,
});

export function AuthProvider({ children }) {
  const { getToken } = useAuthHook();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const BASE = import.meta.env.VITE_BACKEND_URL;

  useEffect(() => {
    async function loadUser() {
      try {
        const token = getToken();
        if (!token) {
          setUser(null);
          setLoading(false);
          return;
        }

        const res = await fetch(`${BASE}/auth/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          setUser(null);
          return;
        }

        const data = await res.json();
        setUser(data);
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    loadUser();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuthContext = () => useContext(AuthContext);