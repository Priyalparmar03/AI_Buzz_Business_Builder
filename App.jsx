import { useState, useEffect, createContext, useContext } from "react";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import ProjectView from "./pages/ProjectView";

// ─── Auth Context ───────────────────────────────────────────────────────────
const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

const API = import.meta.env.VITE_API_URL || "http://localhost:5000/api";
export { API };

// ─── Simple Router ──────────────────────────────────────────────────────────
function Router({ page, setPage }) {
  const { user } = useAuth();

  if (!user) {
    if (page === "register") return <Register setPage={setPage} />;
    return <Login setPage={setPage} />;
  }

  if (page === "history") return <History setPage={setPage} />;
  if (page?.startsWith("project:")) return <ProjectView projectId={page.split(":")[1]} setPage={setPage} />;
  return <Dashboard setPage={setPage} />;
}

// ─── App Root ───────────────────────────────────────────────────────────────
export default function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("token") || null);
  const [page, setPage] = useState("dashboard");
  const [loading, setLoading] = useState(true);

  // Restore session
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    fetch(`${API}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.user) setUser(data.user);
        else logout();
      })
      .catch(logout)
      .finally(() => setLoading(false));
  }, [token]);

  function login(userData, jwt) {
    localStorage.setItem("token", jwt);
    setToken(jwt);
    setUser(userData);
    setPage("dashboard");
  }

  function logout() {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setPage("login");
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#0F0F1A" }}>
        <div style={{ textAlign: "center" }}>
          <div className="spinner" />
          <p style={{ color: "#8b8ba7", marginTop: "1rem" }}>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      <Router page={page} setPage={setPage} />
    </AuthContext.Provider>
  );
}