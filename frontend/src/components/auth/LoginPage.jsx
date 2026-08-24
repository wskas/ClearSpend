import { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useFormik } from "formik";
import api, { getErrorMessage } from "../../lib/api.js";
import { setTokens } from "../../lib/auth.js";
import { AuthShell, TextInput, SubmitButton, FormError } from "./AuthShell.jsx";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState("");

  // Return the user to wherever RequireAuth bounced them from.
  const from = location.state?.from?.pathname || "/";

  const formik = useFormik({
    initialValues: { email: "", password: "" },
    validate: (values) => {
      const errors = {};
      if (!values.email) errors.email = "Required";
      if (!values.password) errors.password = "Required";
      return errors;
    },
    onSubmit: async (values, { setSubmitting }) => {
      setFormError("");
      try {
        // USERNAME_FIELD is 'email', so SimpleJWT's token endpoint expects
        // { email, password }.
        const res = await api.post("/auth/token/", values);
        setTokens({ access: res.data.access, refresh: res.data.refresh });
        navigate(from, { replace: true });
      } catch (err) {
        setFormError(getErrorMessage(err, "Invalid email or password."));
      } finally {
        setSubmitting(false);
      }
    },
  });

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Log in to your ClearSpend account"
      footer={<>Don't have an account? <Link to="/register" style={{ fontWeight: 600 }}>Sign up</Link></>}
    >
      <form onSubmit={formik.handleSubmit}>
        <FormError message={formError} />
        <TextInput label="Email" name="email" type="email" formik={formik} autoComplete="email" />
        <TextInput label="Password" name="password" type="password" formik={formik} autoComplete="current-password" />
        <SubmitButton disabled={formik.isSubmitting}>
          {formik.isSubmitting ? "Logging in…" : "Log in"}
        </SubmitButton>
      </form>
    </AuthShell>
  );
}
