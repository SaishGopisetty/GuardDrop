const LABELS = {
  pending: "Pending",
  eta_sent: "Driver Near",
  delivered: "Delivered",
  escalating: "Escalating",
  picked_up: "Picked Up",
};

export default function StatusBadge({ status }) {
  return (
    <span className={`badge badge-${status}`}>
      {LABELS[status] || status}
    </span>
  );
}
