import { useEffect, useState } from "react";
import api from "../api/client";

function badgeStyle(accepted) {
  return accepted
    ? { background: "#dcfce7", color: "#166534" }
    : { background: "#fef3c7", color: "#92400e" };
}

export default function Contacts() {
  const [contacts, setContacts] = useState([]);
  const [form, setForm] = useState({ name: "", phone: "" });
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [acceptingId, setAcceptingId] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const loadContacts = async () => {
      try {
        const res = await api.get("/contacts");
        if (!cancelled) {
          setContacts(res.data);
        }
      } catch {
        if (!cancelled) {
          setContacts([]);
        }
      }
    };

    void loadContacts();

    return () => {
      cancelled = true;
    };
  }, []);

  const fetchContacts = async () => {
    const res = await api.get("/contacts");
    setContacts(res.data);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setStatusMessage("");

    try {
      await api.post("/contacts", form);
      setForm({ name: "", phone: "" });
      setStatusMessage("Contact added. Accept it below to enable automatic escalation.");
      await fetchContacts();
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong.");
    }
  };

  const handleAccept = async (contactId) => {
    setError("");
    setStatusMessage("");
    setAcceptingId(contactId);

    try {
      await api.post(`/contacts/${contactId}/accept`);
      setContacts((prev) => prev.map((contact) => (
        contact.id === contactId ? { ...contact, accepted: true } : contact
      )));
      setStatusMessage("Contact accepted. GuardDrop can now escalate to them.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not accept this contact.");
    } finally {
      setAcceptingId(null);
    }
  };

  return (
    <div className="container pb-nav">
      <div className="page-header">
        <h1>Trust Network</h1>
        <p>Accepted contacts are the only people GuardDrop can escalate to automatically.</p>
      </div>

      <div className="card">
        <form onSubmit={handleSubmit}>
          <label>Contact Name</label>
          <input
            placeholder="e.g. Alex (neighbor)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <label>Phone Number</label>
          <input
            placeholder="+1 555 000 0000"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            required
          />
          {error && <p style={{ color: "#ef4444", fontSize: 13, marginBottom: 10 }}>{error}</p>}
          {statusMessage && <p style={{ color: "#166534", fontSize: 13, marginBottom: 10 }}>{statusMessage}</p>}
          <button className="btn-primary" type="submit">Add Contact</button>
        </form>
      </div>

      {contacts.length > 0 && (
        <div>
          <p style={{ fontWeight: 600, marginBottom: 10 }}>Your contacts</p>
          {contacts.map((contact) => (
            <div
              className="card"
              key={contact.id}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{contact.name}</div>
                <div className="text-muted" style={{ marginBottom: 8 }}>{contact.phone}</div>
                <span
                  className="badge"
                  style={badgeStyle(contact.accepted)}
                >
                  {contact.accepted ? "Accepted" : "Pending"}
                </span>
                {!contact.accepted && (
                  <p className="text-muted" style={{ marginTop: 8 }}>
                    Pending contacts will not receive automatic escalation alerts.
                  </p>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
                <span style={{ fontSize: 20 }}>👤</span>
                {!contact.accepted && (
                  <button
                    className="btn-sm"
                    type="button"
                    onClick={() => handleAccept(contact.id)}
                    disabled={acceptingId === contact.id}
                    style={{ background: "#1a1a1a", color: "white" }}
                  >
                    {acceptingId === contact.id ? "Accepting..." : "Accept"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
