import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { loadSettings, saveSettings } from "../utils/persistence";

// Centralized personalization system (V2.1 Milestone 3): theme,
// accent color, workspace density, and animation preference. This is
// the *only* place that owns this state — every setting flows
// through here rather than being read/derived independently by each
// component, and applying it is a single effect below (documentElement
// classes/attributes), not scattered per-component logic. Adding a
// future theme, accent, or preference is a matter of extending the
// option lists and the CSS that responds to them (see index.css),
// not touching this file's shape.

export const THEME_OPTIONS = ["light", "dark", "system"];
export const ACCENT_OPTIONS = ["blue", "purple", "green", "orange"];
export const DENSITY_OPTIONS = ["comfortable", "compact"];
export const ANIMATION_OPTIONS = ["enabled", "disabled"];

const PersonalizationContext = createContext(null);

function systemPrefersDark() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

// Resolves "system" down to an actual light/dark for anything that
// needs a concrete answer (e.g. showing "Dark" as the active option
// under System, or a11y tools that want a real value).
function resolveTheme(theme) {
  if (theme === "system") return systemPrefersDark() ? "dark" : "light";
  return theme;
}

export function PersonalizationProvider({ children }) {
  // Lazy-init from storage once — index.html's inline script (see
  // that file) already applied this same saved state to <html> before
  // first paint, so this doesn't cause a flash; it just brings React's
  // state in sync with what's already on screen.
  const [settings, setSettings] = useState(() => loadSettings());

  const applySetting = useCallback((key, value) => {
    setSettings((previous) => {
      const next = { ...previous, [key]: value };
      saveSettings(next);
      return next;
    });
  }, []);

  const setTheme = useCallback((theme) => applySetting("theme", theme), [applySetting]);
  const setAccent = useCallback((accent) => applySetting("accent", accent), [applySetting]);
  const setDensity = useCallback((density) => applySetting("density", density), [applySetting]);
  const setAnimations = useCallback(
    (animations) => applySetting("animations", animations),
    [applySetting]
  );

  // Applies every setting to <html> as a class/data-attribute, which
  // is what index.css's theme, accent, density, and motion rules key
  // off of. This is the single place that touches documentElement —
  // no component reaches for `document.documentElement` on its own.
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", resolveTheme(settings.theme) === "dark");
    root.setAttribute("data-accent", settings.accent);
    root.setAttribute("data-density", settings.density);
    root.setAttribute("data-motion", settings.animations);
  }, [settings]);

  // "System" tracks the OS preference live — if the user's system
  // switches (e.g. sunset-triggered dark mode) while theme is set to
  // "system", the workspace should follow without needing a refresh.
  useEffect(() => {
    if (settings.theme !== "system" || !window.matchMedia) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      document.documentElement.classList.toggle("dark", media.matches);
    };
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, [settings.theme]);

  const value = useMemo(
    () => ({
      theme: settings.theme,
      resolvedTheme: resolveTheme(settings.theme),
      accent: settings.accent,
      density: settings.density,
      animations: settings.animations,
      setTheme,
      setAccent,
      setDensity,
      setAnimations,
    }),
    [settings, setTheme, setAccent, setDensity, setAnimations]
  );

  return (
    <PersonalizationContext.Provider value={value}>{children}</PersonalizationContext.Provider>
  );
}

export function usePersonalization() {
  const context = useContext(PersonalizationContext);
  if (!context) {
    throw new Error("usePersonalization must be used within a PersonalizationProvider");
  }
  return context;
}
