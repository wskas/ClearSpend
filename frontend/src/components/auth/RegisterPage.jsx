import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useFormik } from "formik";
import api, { getErrorMessage } from "../../lib/api.js";
import { setTokens } from "../../lib/auth.js";
import { useCurrencies, FALLBACK_CURRENCIES } from "../../hooks/queries.js";
import { AuthShell, TextInput, SelectInput, SubmitButton, FormError } from "./AuthShell.jsx";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [formError, setFormError] = useState("");
  // Served by the backend; falls back to the built-in list if unreachable.
  const { data: currencies } = useCurrencies();

  const formik = useFormik({
    initialValues: { email: "", username: "", password: "", base_currency: "USD" },
    validate: (values) => {
      const errors = {};
      if (!values.email) errors.email = "Required";
      if (!values.username) errors.username = "Required";
      if (!values.password) errors.password = "Required";
      return errors;
    },
    onSubmit: async (values, { setSubmitting, setErrors }) => {
      setFormError("");
      try {
        await api.post("/auth/register/", values);
        // Register returns the profile, not tokens — immediately log in so
        // the user lands on the dashboard (PRD: register → dashboard).
        const res = await api.post("/auth/token/", {
          email: values.email,
          password: values.password,
        });
        setTokens({ access: res.data.access, refresh: res.data.refresh });
        navigate("/", { replace: true });
      } catch (err) {
        // Map DRF field errors (e.g. duplicate email, weak password) back
        // onto the matching form fields; show anything else as a banner.
        const data = err.response?.data;
        if (data && typeof data === "object" && !Array.isArray(data)) {
          const fieldErrors = {};
          for (const key of Object.keys(values)) {
            if (data[key]) fieldErrors[key] = Array.isArray(data[key]) ? data[key][0] : String(data[key]);
          }
          if (Object.keys(fieldErrors).length) setErrors(fieldErrors);
        }
        setFormError(getErrorMessage(err, "Could not create your account."));
      } finally {
        setSubmitting(false);
      }
    },
  });

  return (
    <AuthShell
      title="Create your account"
      subtitle="Start tracking your subscriptions"
      footer={<>Already have an account? <Link to="/login" style={{ fontWeight: 600 }}>Log in</Link></>}
    >
      <form onSubmit={formik.handleSubmit}>
        <FormError message={formError} />
        <TextInput label="Email" name="email" type="email" formik={formik} autoComplete="email" />
        <TextInput label="Username" name="username" formik={formik} autoComplete="username" />
        <TextInput label="Password" name="password" type="password" formik={formik} autoComplete="new-password" />
        <SelectInput label="Base currency" name="base_currency" formik={formik} options={currencies ?? FALLBACK_CURRENCIES} />
        <SubmitButton disabled={formik.isSubmitting}>
          {formik.isSubmitting ? "Creating account…" : "Sign up"}
        </SubmitButton>
      </form>
    </AuthShell>
  );
}
