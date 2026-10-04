import { LEARN_ACTIONS, LEARN_DEPTHS } from "../utils/learnState.js";

const BUTTON_BASE_CLASSES =
  "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40";

function LearnActionBar({
  activeAction = null,
  activeDepth = "standard",
  onAction,
  onResetAction,
  onDepthChange,
  disabled = false,
  loadingAction = null,
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-y border-slate-100 py-3">
      {/* Contextual actions */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Focus:
        </span>

        {LEARN_ACTIONS.map((action) => {
          const isActive = activeAction === action.id;
          const isLoadingThis = loadingAction === action.id;

          return (
            <button
              key={action.id}
              type="button"
              disabled={disabled}
              onClick={() => onAction?.(action.id)}
              title={action.description}
              className={`${BUTTON_BASE_CLASSES} ${
                isActive
                  ? "bg-accent-600 text-white shadow-sm hover:bg-accent-700"
                  : "border border-slate-200 bg-surface text-slate-700 hover:bg-slate-100"
              }`}
            >
              {isLoadingThis && (
                <span
                  className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                  aria-hidden="true"
                />
              )}
              {action.label}
            </button>
          );
        })}

        {activeAction && (
          <button
            type="button"
            disabled={disabled}
            onClick={onResetAction}
            className="ml-1 rounded px-2 py-1 text-xs text-slate-500 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            title="Return to the standard grounded explanation"
          >
            Reset
          </button>
        )}
      </div>

      {/* Depth selector */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Depth:
        </span>
        <div className="inline-flex rounded-md border border-slate-200 bg-slate-50/80 p-0.5" role="group">
          {LEARN_DEPTHS.map((depth) => {
            const isSelected = activeDepth === depth.id;
            return (
              <button
                key={depth.id}
                type="button"
                disabled={disabled}
                onClick={() => onDepthChange?.(depth.id)}
                title={depth.description}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 ${
                  isSelected
                    ? "bg-surface text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                } disabled:cursor-not-allowed disabled:opacity-50`}
              >
                {depth.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default LearnActionBar;
