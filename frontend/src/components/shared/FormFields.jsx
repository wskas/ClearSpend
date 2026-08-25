// Theme-aware form controls bound to a Formik instance. Shared by the
// subscription and category forms.

function baseStyle(t, hasError) {
  return {
    background: t.cardAlt,
    border: `1px solid ${hasError ? t.red : t.border}`,
    color: t.text,
  };
}

function Label({ t, children }) {
  return <span className="text-[12px] font-semibold" style={{ color: t.textMuted }}>{children}</span>;
}

function Error({ t, message }) {
  if (!message) return null;
  return <span className="text-[11.5px]" style={{ color: t.red }}>{message}</span>;
}

export function Field({ t, label, name, formik, type = "text", ...rest }) {
  const err = formik.touched[name] && formik.errors[name];
  return (
    <label className="block mb-3">
      <Label t={t}>{label}</Label>
      <input
        name={name}
        type={type}
        value={formik.values[name] ?? ""}
        onChange={formik.handleChange}
        onBlur={formik.handleBlur}
        className="w-full mt-1 rounded-lg px-3 py-2 text-[13.5px] outline-none"
        style={baseStyle(t, err)}
        {...rest}
      />
      <Error t={t} message={err} />
    </label>
  );
}

export function Select({ t, label, name, formik, children }) {
  const err = formik.touched[name] && formik.errors[name];
  return (
    <label className="block mb-3">
      <Label t={t}>{label}</Label>
      <select
        name={name}
        value={formik.values[name] ?? ""}
        onChange={formik.handleChange}
        onBlur={formik.handleBlur}
        className="w-full mt-1 rounded-lg px-3 py-2 text-[13.5px] outline-none"
        style={baseStyle(t, err)}
      >
        {children}
      </select>
      <Error t={t} message={err} />
    </label>
  );
}

export function ColorField({ t, label, name, formik }) {
  const err = formik.touched[name] && formik.errors[name];
  const value = formik.values[name] || "#3457D5";
  return (
    <label className="block mb-3">
      <Label t={t}>{label}</Label>
      <div className="flex items-center gap-2 mt-1">
        <input
          type="color"
          name={name}
          value={value}
          onChange={formik.handleChange}
          className="rounded-lg"
          style={{ width: 42, height: 38, background: t.cardAlt, border: `1px solid ${t.border}` }}
        />
        <input
          name={name}
          value={value}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          className="flex-1 rounded-lg px-3 py-2 text-[13.5px] outline-none"
          style={baseStyle(t, err)}
        />
      </div>
      <Error t={t} message={err} />
    </label>
  );
}

export function FormBanner({ t, message }) {
  if (!message) return null;
  return (
    <div className="rounded-lg px-3 py-2 mb-3 text-[12.5px]" style={{ background: t.redSoft, color: t.red }}>
      {message}
    </div>
  );
}

export function FormActions({ t, onCancel, submitting, submitLabel = "Save" }) {
  return (
    <div className="flex items-center justify-end gap-2 mt-4">
      <button
        type="button"
        onClick={onCancel}
        className="rounded-lg px-3.5 py-2 text-[13px] font-semibold"
        style={{ border: `1px solid ${t.border}`, color: t.textMuted }}
      >
        Cancel
      </button>
      <button
        type="submit"
        disabled={submitting}
        className="rounded-lg px-4 py-2 text-[13px] font-semibold text-white"
        style={{ background: t.primary, opacity: submitting ? 0.6 : 1 }}
      >
        {submitting ? "Saving…" : submitLabel}
      </button>
    </div>
  );
}
