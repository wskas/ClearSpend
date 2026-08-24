export default function CardHeader({ t, label, tooltip, pill }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[12.5px] font-semibold" title={tooltip} style={{ color: t.textMuted }}>
        {label}
      </span>
      <span
        className="text-[11px] font-medium rounded-full px-2 py-0.5"
        style={{ background: t.cardAlt, color: t.textMuted }}
      >
        {pill}
      </span>
    </div>
  );
}
