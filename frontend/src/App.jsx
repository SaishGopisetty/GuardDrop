import { useCallback, useEffect, useRef, useState } from "react";
import { clearStoredSession, getWebSocketUrl, readStoredSession, writeStoredSession } from "./api/client";
import ToastStack from "./components/Toast";
import Contacts from "./pages/Contacts";
import Auth from "./pages/Auth";
import Home from "./pages/Home";
import NewDelivery from "./pages/NewDelivery";
import Profile from "./pages/Profile";
import "./index.css";

export default function App() {
  const [session, setSession] = useState(() => readStoredSession());
  const [page, setPage] = useState("home");
  const [lastEvent, setLastEvent] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const user = session?.user ?? null;

  const resetSession = useCallback(() => {
    clearTimeout(reconnectRef.current);
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    clearStoredSession();
    setSession(null);
    setPage("home");
    setLastEvent(null);
    setToasts([]);
    setWsConnected(false);
  }, []);

  const pushToast = useCallback((event) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, ...event }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 5000);
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => resetSession();
    window.addEventListener("guarddrop:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("guarddrop:unauthorized", handleUnauthorized);
  }, [resetSession]);

  useEffect(() => {
    if (!session?.user?.id || !session?.access_token) return;

    let cancelled = false;

    const connectWebSocket = () => {
      if (cancelled) return;

      const ws = new WebSocket(getWebSocketUrl(session.user.id, session.access_token));
      wsRef.current = ws;

      ws.onopen = () => {
        if (!cancelled) {
          setWsConnected(true);
        }
      };

      ws.onmessage = (message) => {
        const event = JSON.parse(message.data);
        setLastEvent(event);
        pushToast(event);

        if (window.Notification?.permission === "granted") {
          new Notification(event.title, { body: event.message });
        }
      };

      ws.onclose = (closeEvent) => {
        if (cancelled) return;

        setWsConnected(false);
        if (closeEvent.code === 1008) {
          resetSession();
          return;
        }

        reconnectRef.current = window.setTimeout(connectWebSocket, 3000);
      };

      ws.onerror = () => ws.close();
    };

    if (window.Notification?.permission === "default") {
      void window.Notification.requestPermission();
    }

    connectWebSocket();

    return () => {
      cancelled = true;
      clearTimeout(reconnectRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [pushToast, resetSession, session]);

  const handleLogin = useCallback((nextSession) => {
    writeStoredSession(nextSession);
    setSession(nextSession);
    setPage("home");
  }, []);

  const handleLogout = useCallback(() => {
    resetSession();
  }, [resetSession]);

  if (!user) {
    return <Auth onLogin={handleLogin} />;
  }

  const tabs = [
    { id: "home", icon: "📦", label: "Deliveries" },
    { id: "new", icon: "+", label: "New" },
    { id: "contacts", icon: "👥", label: "Contacts" },
    { id: "profile", icon: "👤", label: "Profile" },
  ];

  return (
    <>
      <nav style={{ justifyContent: "space-between" }}>
        <div className="logo">Guard<span>Drop</span></div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 12, color: "#aaa", display: "flex", alignItems: "center" }}>
            <span className={`ws-dot ${wsConnected ? "connected" : "disconnected"}`} />
            {wsConnected ? "Live" : "Connecting..."}
          </span>
          <button
            onClick={handleLogout}
            style={{
              background: "none",
              color: "#999",
              fontSize: 13,
              padding: "6px 10px",
              width: "auto",
              border: "1px solid #444",
              borderRadius: 8,
            }}
          >
            Log out
          </button>
        </div>
      </nav>

      <ToastStack toasts={toasts} />

      {page === "home" && <Home lastEvent={lastEvent} />}
      {page === "new" && <NewDelivery onNavigate={setPage} />}
      {page === "contacts" && <Contacts />}
      {page === "profile" && <Profile user={user} onLogout={handleLogout} />}

      <div className="bottom-nav">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={page === tab.id ? "active" : ""}
            onClick={() => setPage(tab.id)}
          >
            <span className="icon">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>
    </>
  );
}
