import { ROUTES, routeHref } from "../router/useHashRoute";

const NAV_ITEMS = [
  { route: ROUTES.HOME, label: "Home" },
  { route: ROUTES.STUDY, label: "Study" },
  { route: ROUTES.CHAT, label: "Chat" },
];

// Recall and Revision aren't implemented in this milestone (see the
// V2.4 Milestone 1 brief), but showing them here, disabled, makes the
// eventual five-item nav (Home | Study | Chat | Recall | Revision)
// visible as the direction the app is heading. Turning one "on" later
// is moving its label from this list into NAV_ITEMS above with a real
// route and a page component — not a nav redesign.
const UPCOMING_ITEMS = ["Recall", "Revision"];

const NAV_LINK_CLASSES =
  "rounded-full px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset";

function AppNav({ route }) {
  return (
    <nav aria-label="Primary" className="flex flex-wrap items-center gap-1">
      {NAV_ITEMS.map((item) => {
        const isActive = item.route === route;
        return (
          <a
            key={item.route}
            href={routeHref(item.route)}
            aria-current={isActive ? "page" : undefined}
            className={`${NAV_LINK_CLASSES} ${
              isActive ? "bg-accent-600 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            {item.label}
          </a>
        );
      })}
      {UPCOMING_ITEMS.map((label) => (
        <span
          key={label}
          title="Coming soon"
          aria-disabled="true"
          className={`${NAV_LINK_CLASSES} cursor-not-allowed select-none text-slate-300`}
        >
          {label}
        </span>
      ))}
    </nav>
  );
}

export default AppNav;
