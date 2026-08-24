import { THEME } from "../../theme/token.js";

// Auth pages use the light theme — the dashboard's dark-mode toggle lives
// inside AppShell, which isn't mounted until after login.
const t = THEME.light;

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div
      className="flex items-center justify-center p-6"
      style={{ background: t.bg, color: t.text, minHeight: "100vh", fontFamily: "'Inter', sans-serif" }}
    >
      <div className="w-full" style={{ maxWidth: 380 }}>
        <div className="flex items-center gap-2 justify-center mb-6">
          <div
            className="flex items-center justify-center rounded-lg"
            style={{ width: 30, height: 30, background: t.primary, color: "#fff", fontWeight: 800, fontSize: 14 }}
          >
            C
          </div>
          <span className="font-bold text-[15px]">ClearSpend</span>
        </div>

        <div className="rounded-2xl p-6" style={{ background: t.card, border: `1px solid ${t.border}`, boxShadow: t.shadow }}>
          <h1 className="text-[18px] font-bold">{title}</h1>
          <p className="text-[13px] mt-1" style={{ color: t.textMuted }}>{subtitle}</p>
          <div className="mt-5">{children}</div>
        </div>

        {footer && (
          <p className="text-[13px] text-center mt-5" style={{ color: t.textMuted }}>
            {footer}
          </p>
        )}
      </div>
    </div>
  );
}

const fieldStyle = (hasError) => ({
  background: t.cardAlt,
  border: `1px solid ${hasError ? t.red : t.border}`,
  color: t.text,
});

export function TextInput({ label, name, formik, type = "text", ...rest }) {
  const error = formik.touched[name] && formik.errors[name];
  return (
    <label className="block mb-3">
      <span className="text-[12px] font-semibold" style={{ color: t.textMuted }}>{label}</span>
      <input
        name={name}
        type={type}
        value={formik.values[name]}
        onChange={formik.handleChange}
        onBlur={formik.handleBlur}
        className="w-full mt-1 rounded-lg px-3 py-2 text-[13.5px] outline-none"
        style={fieldStyle(error)}
        {...rest}
      />
      {error && <span className="text-[11.5px]" style={{ color: t.red }}>{error}</span>}
    </label>
  );
}

export function SelectInput({ label, name, formik, options }) {
  const error = formik.touched[name] && formik.errors[name];
  return (
    <label className="block mb-3">
      <span className="text-[12px] font-semibold" style={{ color: t.textMuted }}>{label}</span>
      <select
        name={name}
        value={formik.values[name]}
        onChange={formik.handleChange}
        onBlur={formik.handleBlur}
        className="w-full mt-1 rounded-lg px-3 py-2 text-[13.5px] outline-none"
        style={fieldStyle(error)}
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
      {error && <span className="text-[11.5px]" style={{ color: t.red }}>{error}</span>}
    </label>
  );
}

export function SubmitButton({ children, disabled }) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className="cs-tap w-full mt-2 rounded-lg py-2.5 text-[13.5px] font-semibold"
      style={{ background: t.primary, color: "#fff", opacity: disabled ? 0.6 : 1 }}
    >
      {children}
    </button>
  );
}

export function FormError({ message }) {
  if (!message) return null;
  return (
    <div
      className="rounded-lg px-3 py-2 mb-3 text-[12.5px]"
      style={{ background: t.redSoft, color: t.red }}
    >
      {message}
    </div>
  );
}
