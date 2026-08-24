import { useState } from "react";
import { useFormik } from "formik";
import Modal from "../shared/Modal.jsx";
import { Field, Select, FormBanner, FormActions } from "../shared/FormFields.jsx";
import { useCreateSubscription, useUpdateSubscription } from "../../hooks/mutations.js";
import { getErrorMessage, getFieldErrors } from "../../lib/api.js";

// Keep in sync with SUPPORTED_CURRENCIES in the backend command.
const CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "SGD", "IDR", "HKD"];
const CYCLES = [
  ["monthly", "Monthly"],
  ["yearly", "Yearly"],
  ["custom", "Custom"],
];

export default function SubscriptionForm({ t, subscription, categories, onClose }) {
  const isEdit = Boolean(subscription);
  const createM = useCreateSubscription();
  const updateM = useUpdateSubscription();
  const [formError, setFormError] = useState("");

  const formik = useFormik({
    initialValues: {
      name: subscription?.name ?? "",
      amount: subscription?.amount ?? "",
      original_currency: subscription?.currency ?? "USD",
      category: subscription?.categoryId ?? "",
      billing_cycle: subscription?.billingCycle ?? "monthly",
      custom_interval_days: subscription?.customIntervalDays ?? "",
      start_date: subscription?.startDate ?? "",
    },
    validate: (v) => {
      const e = {};
      if (!v.name.trim()) e.name = "Required";
      if (v.amount === "" || Number(v.amount) <= 0) e.amount = "Enter an amount greater than 0";
      if (!v.start_date) e.start_date = "Required";
      if (v.billing_cycle === "custom" && (!v.custom_interval_days || Number(v.custom_interval_days) <= 0)) {
        e.custom_interval_days = "Required for a custom cycle";
      }
      return e;
    },
    onSubmit: async (values, { setSubmitting, setErrors }) => {
      setFormError("");
      const payload = {
        name: values.name,
        amount: values.amount,
        original_currency: values.original_currency,
        category: values.category === "" ? null : Number(values.category),
        billing_cycle: values.billing_cycle,
        // Backend rejects custom_interval_days unless the cycle is custom.
        custom_interval_days:
          values.billing_cycle === "custom" ? Number(values.custom_interval_days) : null,
        start_date: values.start_date || null,
      };
      try {
        if (isEdit) {
          await updateM.mutateAsync({ id: subscription.id, ...payload });
        } else {
          await createM.mutateAsync(payload);
        }
        onClose();
      } catch (err) {
        const fieldErrors = getFieldErrors(err);
        if (Object.keys(fieldErrors).length) setErrors(fieldErrors);
        setFormError(getErrorMessage(err, "Could not save the subscription."));
      } finally {
        setSubmitting(false);
      }
    },
  });

  return (
    <Modal t={t} title={isEdit ? "Edit subscription" : "Add subscription"} onClose={onClose}>
      <form onSubmit={formik.handleSubmit}>
        <FormBanner t={t} message={formError} />
        <Field t={t} label="Name" name="name" formik={formik} />

        <div className="grid grid-cols-2 gap-3">
          <Field t={t} label="Amount" name="amount" type="number" step="0.01" min="0" formik={formik} />
          <Select t={t} label="Currency" name="original_currency" formik={formik}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
        </div>

        <Select t={t} label="Category" name="category" formik={formik}>
          <option value="">— None —</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>

        <div className="grid grid-cols-2 gap-3">
          <Select t={t} label="Billing cycle" name="billing_cycle" formik={formik}>
            {CYCLES.map(([val, lbl]) => <option key={val} value={val}>{lbl}</option>)}
          </Select>
          {formik.values.billing_cycle === "custom" && (
            <Field t={t} label="Interval (days)" name="custom_interval_days" type="number" min="1" formik={formik} />
          )}
        </div>

        <Field t={t} label="Start date" name="start_date" type="date" formik={formik} />

        <FormActions
          t={t}
          onCancel={onClose}
          submitting={formik.isSubmitting}
          submitLabel={isEdit ? "Save changes" : "Add subscription"}
        />
      </form>
    </Modal>
  );
}
