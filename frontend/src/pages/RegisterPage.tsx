import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { useAuth } from "../hooks/useAuth";

export default function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "", password_confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const update = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (form.password !== form.password_confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await register({ ...form, username: form.username.trim(), email: form.email.trim() });
      navigate("/documents", { replace: true });
    } catch (err) {
      setError(getErrorMessage(err, "Registration failed."));
    } finally {
      setSubmitting(false);
    }
  };

  const field = "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none";

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">Create an account</h1>
        <p className="mt-1 text-sm text-slate-500">Upload PDFs and ask questions grounded in them.</p>

        <label className="mt-6 block text-sm font-medium text-slate-700">
          Username
          <input value={form.username} onChange={update("username")} autoComplete="username" required className={field} />
        </label>
        <label className="mt-4 block text-sm font-medium text-slate-700">
          Email
          <input type="email" value={form.email} onChange={update("email")} autoComplete="email" required className={field} />
        </label>
        <label className="mt-4 block text-sm font-medium text-slate-700">
          Password
          <input
            type="password"
            value={form.password}
            onChange={update("password")}
            autoComplete="new-password"
            minLength={8}
            required
            className={field}
          />
        </label>
        <label className="mt-4 block text-sm font-medium text-slate-700">
          Confirm password
          <input
            type="password"
            value={form.password_confirm}
            onChange={update("password_confirm")}
            autoComplete="new-password"
            minLength={8}
            required
            className={field}
          />
        </label>

        {error && <p className="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
        >
          {submitting ? "Creating…" : "Register"}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          Already registered?{" "}
          <Link to="/login" className="font-medium text-indigo-600 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
