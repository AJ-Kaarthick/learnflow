import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { PASSWORD_REQUIREMENTS_MESSAGE, getEmailFormatError, getPasswordStrengthError } from "../utils/authValidation";
import Modal from "./Modal";

// Minimal sign-in/sign-up surface (V3 Milestone 1 Phase 2). One modal,
// one form, a single link toggling which of the two actions it
// submits as -- deliberately not two separate dialogs or a dedicated
// route/page, per the brief ("A minimal clean authentication surface
// is sufficient... not a visual redesign"). Dialog chrome (backdrop,
// focus trap, Escape, scroll lock) comes from the shared Modal
// component, same as SettingsPanel and ShortcutsDialog.
function AuthPanel({ onClose }) {
  const { signup, signin, error, clearError } = useAuth();
  const [mode, setMode] = useState("signin"); // signin | signup
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Client-side pre-submit validation (email format, and on signup,
  // password strength) -- catches obviously-invalid input before it
  // ever reaches the network, with the exact same wording the backend
  // would otherwise reject it with (see utils/authValidation.js).
  // Kept separate from AuthContext's `error` (which only ever reflects
  // an actual failed API call) so switching modes or editing a field
  // can clear this one locally without touching that shared state.
  const [validationError, setValidationError] = useState(null);

  const displayedError = validationError || error;

  function handleSwitchMode(nextMode) {
    setMode(nextMode);
    setValidationError(null);
    clearError();
  }

  function handleEmailChange(event) {
    setEmail(event.target.value);
    if (validationError) setValidationError(null);
    if (error) clearError();
  }

  function handlePasswordChange(event) {
    setPassword(event.target.value);
    if (validationError) setValidationError(null);
    if (error) clearError();
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const emailError = getEmailFormatError(email);
    if (emailError) {
      setValidationError(emailError);
      return;
    }
    if (mode === "signup") {
      const passwordError = getPasswordStrengthError(password);
      if (passwordError) {
        setValidationError(passwordError);
        return;
      }
    }

    setSubmitting(true);
    const succeeded = mode === "signup" ? await signup(email, password) : await signin(email, password);
    setSubmitting(false);
    if (succeeded) onClose();
  }

  return (
    <Modal title={mode === "signup" ? "Create your account" : "Sign in"} onClose={onClose} maxWidthClassName="max-w-sm">
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="space-y-1">
          <label htmlFor="auth-email" className="block text-xs font-medium text-slate-500">
            Email
          </label>
          <input
            id="auth-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={handleEmailChange}
            className="w-full min-w-0 rounded-md border border-slate-300 bg-surface px-3 py-1.5 text-sm text-slate-900 caret-accent-600 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="auth-password" className="block text-xs font-medium text-slate-500">
            Password
          </label>
          <input
            id="auth-password"
            type="password"
            required
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            value={password}
            onChange={handlePasswordChange}
            className="w-full min-w-0 rounded-md border border-slate-300 bg-surface px-3 py-1.5 text-sm text-slate-900 caret-accent-600 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          />
          {mode === "signup" && <p className="text-xs text-slate-400">{PASSWORD_REQUIREMENTS_MESSAGE}</p>}
        </div>

        {displayedError && <p className="text-sm text-red-600">{displayedError}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:opacity-40"
        >
          {submitting ? "Please wait..." : mode === "signup" ? "Create account" : "Sign in"}
        </button>

        <p className="text-center text-xs text-slate-500">
          {mode === "signup" ? (
            <>
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => handleSwitchMode("signin")}
                className="font-medium text-accent-600 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
              >
                Sign in
              </button>
            </>
          ) : (
            <>
              Don&apos;t have an account?{" "}
              <button
                type="button"
                onClick={() => handleSwitchMode("signup")}
                className="font-medium text-accent-600 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
              >
                Sign up
              </button>
            </>
          )}
        </p>
      </form>
    </Modal>
  );
}

export default AuthPanel;
