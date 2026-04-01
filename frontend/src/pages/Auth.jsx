import { useState } from "react";
import api from "../api/client";

export default function Auth({ onLogin }) {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [form, setForm] = useState({ name: "", phone: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = mode === "login" ? "/login" : "/signup";
      const payload = mode === "login"
        ? { email: form.email, password: form.password }
        : { name: form.name, phone: form.phone, email: form.email, password: form.password };

      const res = await api.post(endpoint, payload);
      onLogin(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "24px 16px",
      background: "#f5f5f0",
    }}>
      {/* Logo */}
      <div style={{ marginBottom: 32, textAlign: "center" }}>
        <div style={{ fontSize: 48, marginBottom: 8 }}>📦</div>
        <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-1px" }}>
          Guard<span style={{ color: "#f59e0b" }}>Drop</span>
        </div>
        <p style={{ color: "#999", fontSize: 14, marginTop: 6 }}>
          Smart last-mile delivery protection
        </p>
      </div>

      {/* Card */}
      <div className="card" style={{ width: "100%", maxWidth: 400 }}>
        {/* Toggle */}
        <div style={{
          display: "flex",
          background: "#f5f5f0",
          borderRadius: 10,
          padding: 4,
          marginBottom: 24,
        }}>
          {["login", "signup"].map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(""); }}
              style={{
                flex: 1,
                background: mode === m ? "white" : "transparent",
                color: mode === m ? "#1a1a1a" : "#999",
                boxShadow: mode === m ? "0 1px 4px rgba(0,0,0,0.1)" : "none",
                borderRadius: 8,
                padding: "8px 0",
                fontSize: 14,
                width: "auto",
              }}
            >
              {m === "login" ? "Log In" : "Sign Up"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit}>
          {mode === "signup" && (
            <>
              <label>Name</label>
              <input placeholder="Your name" value={form.name} onChange={set("name")} required />
              <label>Phone</label>
              <input placeholder="+1 555 000 0000" value={form.phone} onChange={set("phone")} required />
            </>
          )}

          <label>Email</label>
          <input type="email" placeholder="you@email.com" value={form.email} onChange={set("email")} required />

          <label>Password</label>
          <input type="password" placeholder="••••••••" value={form.password} onChange={set("password")} required />

          {error && (
            <p style={{ color: "#ef4444", fontSize: 13, marginBottom: 12 }}>{error}</p>
          )}

          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? "Please wait..." : mode === "login" ? "Log In" : "Create Account"}
          </button>
        </form>
      </div>
    </div>
  );
}
