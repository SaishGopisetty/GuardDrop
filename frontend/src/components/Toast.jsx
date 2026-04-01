const TOAST_STYLES = {
  eta_sent: { cls: "toast-warning", icon: "🚚" },
  delivered: { cls: "toast-warning", icon: "📦" },
  escalating: { cls: "toast-danger", icon: "🚨" },
  secondary_alerted: { cls: "toast-danger", icon: "🚨" },
  secondary_alert_skipped: { cls: "toast-warning", icon: "⚠️" },
  secondary_alert_failed: { cls: "toast-danger", icon: "⚠️" },
  picked_up: { cls: "toast-success", icon: "✅" },
};

export default function ToastStack({ toasts }) {
  if (toasts.length === 0) return null;

  return (
    <div className="toast-stack">
      {toasts.map((toast) => {
        const style = TOAST_STYLES[toast.type] || { cls: "", icon: "📢" };
        return (
          <div key={toast.id} className={`toast ${style.cls}`}>
            <span className="toast-icon">{style.icon}</span>
            <div className="toast-body">
              <div className="toast-title">{toast.title}</div>
              <div className="toast-msg">{toast.message}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
