export default function Card({ t, children, className = "", style = {} }) {
  return (
    <div
      className={`rounded-2xl p-5 ${className}`}
      style={{ background: t.card, border: `1px solid ${t.border}`, boxShadow: t.shadow, ...style }}
    >
      {children}
    </div>
  );
}
