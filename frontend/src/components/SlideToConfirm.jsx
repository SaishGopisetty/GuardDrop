import { useRef, useState } from "react";

export default function SlideToConfirm({ onConfirm }) {
  const trackRef = useRef(null);
  const [offset, setOffset] = useState(0);
  const [confirmed, setConfirmed] = useState(false);
  const dragging = useRef(false);
  const startX = useRef(0);

  const getMax = () => {
    if (!trackRef.current) return 200;
    return trackRef.current.offsetWidth - 60;
  };

  const onMouseDown = (e) => {
    dragging.current = true;
    startX.current = e.clientX || e.touches[0].clientX;
  };

  const onMouseMove = (e) => {
    if (!dragging.current) return;
    const x = (e.clientX || e.touches?.[0]?.clientX) - startX.current;
    const clamped = Math.max(0, Math.min(x, getMax()));
    setOffset(clamped);
  };

  const onMouseUp = () => {
    if (!dragging.current) return;
    dragging.current = false;
    if (offset >= getMax() * 0.85) {
      setOffset(getMax());
      setConfirmed(true);
      onConfirm();
    } else {
      setOffset(0);
    }
  };

  if (confirmed) {
    return (
      <div className="slide-wrapper" style={{ background: "#dcfce7", borderColor: "#16a34a" }}>
        <div className="slide-track" style={{ color: "#15803d" }}>Confirmed!</div>
      </div>
    );
  }

  return (
    <div
      className="slide-wrapper"
      ref={trackRef}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
      onTouchMove={onMouseMove}
      onTouchEnd={onMouseUp}
    >
      <div className="slide-track">Slide to confirm pickup</div>
      <div
        className="slide-thumb"
        style={{ left: `${offset + 4}px` }}
        onMouseDown={onMouseDown}
        onTouchStart={onMouseDown}
      >
        📦
      </div>
    </div>
  );
}
