export default function Profile({ user, onLogout }) {
  return (
    <div className="container pb-nav">
      <div className="page-header">
        <h1>Profile</h1>
      </div>

      <div className="card" style={{ textAlign: "center" }}>
        <div style={{ fontSize: 52, marginBottom: 12 }}>👤</div>
        <div style={{ fontWeight: 700, fontSize: 18 }}>{user.name}</div>
        <div className="text-muted" style={{ marginTop: 4 }}>{user.email}</div>
      </div>

      <div className="card" style={{ background: "#fefce8", border: "1.5px solid #fde047" }}>
        <p style={{ fontSize: 13, color: "#713f12" }}>
          <strong>Session note:</strong> Your login is saved in the browser. You'll stay logged in even after a refresh.
        </p>
      </div>

      <button className="btn-danger" onClick={onLogout}>Log Out</button>
    </div>
  );
}
