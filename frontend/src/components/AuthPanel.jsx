import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  PASSWORD_REQUIREMENTS_MESSAGE,
  getEmailFormatError,
  getPasswordConfirmationError,
  getPasswordInputType,
  getPasswordStrengthError,
  getPasswordVisibilityToggleAriaLabel,
} from "../utils/authValidation";
import Modal from "./Modal";

// Heroicons "eye" / "eye-slash" (20/solid, mini), matching the
// fill="currentColor" solid-icon convention already used elsewhere in
// this project (see Modal.jsx's close icon and TopBar.jsx's settings
// icon) rather than introducing an icon library dependency for two
// glyphs.
function EyeIcon(props) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true" {...props}>
      <path d="M10 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
      <path
        fillRule="evenodd"
        d="M.664 10.59a1.651 1.651 0 0 1 0-1.186A10.004 10.004 0 0 1 10 3c4.257 0 7.893 2.66 9.336 6.41.147.381.147.804 0 1.186A10.004 10.004 0 0 1 10 17c-4.257 0-7.893-2.66-9.336-6.41ZM14 10a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function EyeOffIcon(props) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true" {...props}>
      <path
        fillRule="evenodd"
        d="M3.28 2.22a.75.75 0 0 0-1.06 1.06l14.5 14.5a.75.75 0 1 0 1.06-1.06l-1.745-1.745a10.029 10.029 0 0 0 3.3-4.38 1.651 1.651 0 0 0 0-1.185A10.004 10.004 0 0 0 9.999 3a9.956 9.956 0 0 0-4.744 1.194L3.28 2.22ZM7.752 6.69l1.092 1.092a2.5 2.5 0 0 1 3.374 3.373l1.091 1.092a4 4 0 0 0-5.557-5.557Z"
        clipRule="evenodd"
      />
      <path d="M10.748 13.93l2.523 2.523a9.987 9.987 0 0 1-3.27.547c-4.258 0-7.894-2.66-9.337-6.41a1.651 1.651 0 0 1 0-1.186A10.007 10.007 0 0 1 2.839 6.02L6.07 9.252a4 4 0 0 0 4.678 4.678Z" />
    </svg>
  );
}

// Shared by both the "Password" and "Confirm password" fields (V3
// Milestone 1 Phase 3) -- since AuthPanel already renders a single
// password field for both signin and signup (the markup was never
// duplicated by mode, only its autoComplete/copy), this is also what
// gives the sign-in modal's own password field the same show/hide
// control for free, per the brief's "reuse the existing
// implementation/style where appropriate rather than creating
// duplicate patterns" -- there was no prior pattern to reuse, so this
// component *is* that one shared pattern going forward. `type` and the
// toggle button's `aria-label` are both wired straight to
// authValidation.js's pure helpers, so the exact logic driving the
// UI is what utils/authValidation.test.js exercises.
function PasswordField({ id, label, value, onChange, autoComplete, visible, onToggleVisible, helperText }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-xs font-medium text-slate-500">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={getPasswordInputType(visible)}
          required
          autoComplete={autoComplete}
          value={value}
          onChange={onChange}
          className="w-full min-w-0 rounded-md border border-slate-300 bg-surface px-3 py-1.5 pr-9 text-sm text-slate-900 caret-accent-600 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
        />
        {/* type="button" is load-bearing here: inside a <form>, a
            button with no explicit type defaults to type="submit",
            which would submit the form (and attempt a signin/signup
            with whatever's currently in the fields) every time
            someone just wanted to peek at their password. */}
        <button
          type="button"
          onClick={onToggleVisible}
          aria-label={getPasswordVisibilityToggleAriaLabel(visible, label.toLowerCase())}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex items-center px-2.5 text-slate-400 hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset rounded-md"
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
      {helperText && <p className="text-xs text-slate-400">{helperText}</p>}
    </div>
  );
}

// Minimal sign-in/sign-up surface (V3 Milestone 1 Phase 2). One modal,
// one form, a single link toggling which of the two actions it
// submits as -- deliberately not two separate dialogs or a dedicated
// route/page, per the brief ("A minimal clean authentication surface
// is sufficient... not a visual redesign"). Dialog chrome (backdrop,
// focus trap, Escape, scroll lock) comes from the shared Modal
// component, same as SettingsPanel and ShortcutsDialog.
//
// `initialMode` (V3 Milestone 1 Phase 3) lets a caller open this
// straight into "Create your account" instead of always defaulting to
// "Sign in" -- used by GuestLimitNotice, since someone who just hit a
// guest limit is coming here specifically to sign up, not to log into
// an account they may not have. `introMessage`, shown above the form,
// is what actually explains *why* the panel opened -- reusing the same
// message the guest-limit response itself already produced (see
// api/errors.js's GuestLimitError) rather than inventing a second
// copy of it. Both default to this panel's original behavior
// (plain "Sign in", no intro copy) for every other caller.
function AuthPanel({ onClose, initialMode = "signin", introMessage = null }) {
  const { signup, signin, error, clearError } = useAuth();
  const [mode, setMode] = useState(initialMode); // signin | signup
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Confirm-password only ever matters in signup mode (V3 Milestone 1
  // Phase 3) -- reset on every mode switch so a value typed before
  // flipping to "Sign in" and back doesn't silently linger and get
  // checked against a since-edited password.
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [confirmPasswordVisible, setConfirmPasswordVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  // Client-side pre-submit validation (email format, and on signup,
  // password strength and confirm-password match) -- catches
  // obviously-invalid input before it ever reaches the network, with
  // the exact same wording the backend would otherwise reject it with
  // (see utils/authValidation.js). Kept separate from AuthContext's
  // `error` (which only ever reflects an actual failed API call) so
  // switching modes or editing a field can clear this one locally
  // without touching that shared state.
  const [validationError, setValidationError] = useState(null);

  const displayedError = validationError || error;

  function handleSwitchMode(nextMode) {
    setMode(nextMode);
    setValidationError(null);
    clearError();
    setConfirmPassword("");
    setConfirmPasswordVisible(false);
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

  function handleConfirmPasswordChange(event) {
    setConfirmPassword(event.target.value);
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
      // Confirm-password is checked client-side only, and only ever
      // gates whether `signup` below gets called -- it changes
      // nothing about what's sent over the wire (still just `email`
      // and `password`, see api/auth.js) or what the backend
      // validates, which remains the actual source of truth for
      // credential rules (schemas/auth.py).
      const confirmationError = getPasswordConfirmationError(password, confirmPassword);
      if (confirmationError) {
        setValidationError(confirmationError);
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
        {introMessage && (
          <p className="rounded-md bg-accent-50 px-3 py-2 text-sm text-accent-800">{introMessage}</p>
        )}

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

        <PasswordField
          id="auth-password"
          label="Password"
          value={password}
          onChange={handlePasswordChange}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          visible={passwordVisible}
          onToggleVisible={() => setPasswordVisible((previous) => !previous)}
          helperText={mode === "signup" ? PASSWORD_REQUIREMENTS_MESSAGE : null}
        />

        {mode === "signup" && (
          <PasswordField
            id="auth-confirm-password"
            label="Confirm password"
            value={confirmPassword}
            onChange={handleConfirmPasswordChange}
            autoComplete="new-password"
            visible={confirmPasswordVisible}
            onToggleVisible={() => setConfirmPasswordVisible((previous) => !previous)}
          />
        )}

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
