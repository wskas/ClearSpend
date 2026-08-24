import { useState } from "react";
import { useFormik } from "formik";
import Modal from "../shared/Modal.jsx";
import { Field, ColorField, FormBanner, FormActions } from "../shared/FormFields.jsx";
import { useCreateCategory, useUpdateCategory } from "../../hooks/mutations.js";
import { getErrorMessage, getFieldErrors } from "../../lib/api.js";

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

export default function CategoryForm({ t, category, onClose }) {
  const isEdit = Boolean(category);
  const createM = useCreateCategory();
  const updateM = useUpdateCategory();
  const [formError, setFormError] = useState("");

  const formik = useFormik({
    initialValues: {
      name: category?.name ?? "",
      hex_color_code: category?.hex_color_code ?? "#3457D5",
    },
    validate: (v) => {
      const e = {};
      if (!v.name.trim()) e.name = "Required";
      if (!HEX_RE.test(v.hex_color_code)) e.hex_color_code = "Use a hex color, e.g. #3b82f6";
      return e;
    },
    onSubmit: async (values, { setSubmitting, setErrors }) => {
      setFormError("");
      try {
        if (isEdit) {
          await updateM.mutateAsync({ id: category.id, ...values });
        } else {
          await createM.mutateAsync(values);
        }
        onClose();
      } catch (err) {
        const fieldErrors = getFieldErrors(err);
        if (Object.keys(fieldErrors).length) setErrors(fieldErrors);
        setFormError(getErrorMessage(err, "Could not save the category."));
      } finally {
        setSubmitting(false);
      }
    },
  });

  return (
    <Modal t={t} title={isEdit ? "Edit category" : "Add category"} onClose={onClose}>
      <form onSubmit={formik.handleSubmit}>
        <FormBanner t={t} message={formError} />
        <Field t={t} label="Name" name="name" formik={formik} />
        <ColorField t={t} label="Color" name="hex_color_code" formik={formik} />
        <FormActions
          t={t}
          onCancel={onClose}
          submitting={formik.isSubmitting}
          submitLabel={isEdit ? "Save changes" : "Add category"}
        />
      </form>
    </Modal>
  );
}
