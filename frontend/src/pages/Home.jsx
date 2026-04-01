import { useCallback, useEffect, useState } from "react";
import api from "../api/client";
import SlideToConfirm from "../components/SlideToConfirm";
import StatusBadge from "../components/StatusBadge";

const BASE_STATUS_INFO = {
  pending: { icon: "🕐", text: "Simulation starting - driver will be near soon..." },
  eta_sent: { icon: "🚚", text: "Driver is about 10 minutes away!" },
  delivered: { icon: "📦", text: "Package dropped off. Slide to confirm you picked it up." },
  escalating: { icon: "🚨", text: "A trusted contact was successfully alerted to help secure your package." },
  picked_up: { icon: "✅", text: "Package picked up successfully." },
};

const EVENT_OVERRIDES = {
  escalation_1: { icon: "⏳", text: "Your package is still outside. Please pick it up soon." },
  escalation_2: { icon: "🚨", text: "This package has been unattended for a while." },
  secondary_alert_skipped: {
    icon: "⚠️",
    text: "No accepted trusted contact is available, so GuardDrop could not escalate automatically.",
  },
  secondary_alert_failed: {
    icon: "⚠️",
    text: "GuardDrop tried to alert your trusted contact, but the notification failed.",
  },
};

function getStatusInfo(delivery) {
  if (delivery.status === "delivered" && delivery.latest_event_type && EVENT_OVERRIDES[delivery.latest_event_type]) {
    return EVENT_OVERRIDES[delivery.latest_event_type];
  }
  return BASE_STATUS_INFO[delivery.status] || { icon: "📦", text: "Delivery update received." };
}

export default function Home({ lastEvent }) {
  const [deliveries, setDeliveries] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDeliveries = useCallback(async () => {
    try {
      const res = await api.get("/deliveries");
      setDeliveries([...res.data].reverse());
    } catch {
      setDeliveries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadDeliveries = async () => {
      try {
        const res = await api.get("/deliveries");
        if (!cancelled) {
          setDeliveries([...res.data].reverse());
        }
      } catch {
        if (!cancelled) {
          setDeliveries([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadDeliveries();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!lastEvent) return;
    void fetchDeliveries();
  }, [fetchDeliveries, lastEvent]);

  const confirmPickup = async (deliveryId) => {
    await api.post(`/deliveries/${deliveryId}/pickup`);
    await fetchDeliveries();
  };

  return (
    <div className="container pb-nav">
      <div className="page-header">
        <h1>Your Deliveries</h1>
        <p>System monitors and alerts you automatically</p>
      </div>

      {loading && <p className="text-muted">Loading...</p>}

      {!loading && deliveries.length === 0 && (
        <div className="card text-center">
          <div style={{ fontSize: 40, marginBottom: 8 }}>📭</div>
          <p className="text-muted">No deliveries yet. Tap + to add one.</p>
        </div>
      )}

      {deliveries.map((delivery) => {
        const info = getStatusInfo(delivery);
        return (
          <div
            className="card"
            key={delivery.id}
            style={{
              borderLeft: delivery.status === "escalating" ? "4px solid #ef4444"
                : delivery.status === "delivered" ? "4px solid #f59e0b"
                : delivery.status === "picked_up" ? "4px solid #22c55e"
                : "4px solid #e5e5e5",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: 10,
              }}
            >
              <div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{delivery.retailer}</div>
                <div className="text-muted" style={{ marginTop: 2 }}>#{delivery.tracking_id}</div>
              </div>
              <StatusBadge status={delivery.status} />
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "#f9f9f7",
                borderRadius: 10,
                padding: "10px 12px",
                marginBottom: delivery.status === "delivered" || delivery.status === "escalating" ? 12 : 0,
              }}
            >
              <span style={{ fontSize: 18 }}>{info.icon}</span>
              <span style={{ fontSize: 13, color: "#555" }}>{info.text}</span>
            </div>

            {(delivery.status === "delivered" || delivery.status === "escalating") && (
              <SlideToConfirm onConfirm={() => confirmPickup(delivery.id)} />
            )}
          </div>
        );
      })}
    </div>
  );
}
