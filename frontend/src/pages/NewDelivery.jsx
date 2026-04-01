import { useState } from "react";
import api from "../api/client";

const RETAILERS = ["Walmart", "Amazon", "Target", "Best Buy", "eBay", "Instacart", "FedEx", "UPS", "USPS", "Other"];

export default function NewDelivery({ onNavigate }) {
  const [form, setForm] = useState({ tracking_id: "", retailer: "Walmart" });
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/deliveries", form);
      setSuccess(true);
      window.setTimeout(() => {
        onNavigate("home");
      }, 2500);
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong.");
    }
  };

  return (
    <div className="container pb-nav">
      <div className="page-header">
        <h1>New Delivery</h1>
        <p>Add a package to track</p>
      </div>

      <div className="card">
        <form onSubmit={handleSubmit}>
          <label>Retailer</label>
          <select
            value={form.retailer}
            onChange={(e) => setForm({ ...form, retailer: e.target.value })}
          >
            {RETAILERS.map((retailer) => <option key={retailer}>{retailer}</option>)}
          </select>

          <label>Tracking ID</label>
          <input
            placeholder="e.g. WMT-2026-00142"
            value={form.tracking_id}
            onChange={(e) => setForm({ ...form, tracking_id: e.target.value })}
            required
          />

          {error && <p style={{ color: "#ef4444", fontSize: 13, marginBottom: 10 }}>{error}</p>}

          {success ? (
            <div
              style={{
                background: "#f0fdf4",
                border: "1.5px solid #22c55e",
                borderRadius: 12,
                padding: 16,
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 28, marginBottom: 6 }}>🚀</div>
              <p style={{ color: "#16a34a", fontWeight: 700 }}>Delivery added!</p>
              <p style={{ color: "#555", fontSize: 13, marginTop: 6 }}>
                GuardDrop is now monitoring your package.
                <br />
                You&apos;ll get a browser notification when your driver is near.
              </p>
            </div>
          ) : (
            <button className="btn-primary" type="submit">Add Delivery</button>
          )}
        </form>
      </div>
    </div>
  );
}
