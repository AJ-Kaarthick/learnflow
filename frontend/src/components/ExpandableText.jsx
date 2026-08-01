import { useEffect, useRef, useState } from "react";

// Clamps long text to a few lines with a soft gradient fade instead
// of a hard cutoff, and reveals a "Read more"/"Show less" toggle only
// when the text actually overflows the clamp — short text never shows
// a pointless toggle. `fadeFromClassName` lets the fade blend into
// whatever background this sits on.
function ExpandableText({
  text,
  className = "",
  textClassName = "text-slate-600",
  fadeFromClassName = "from-surface",
}) {
  const [expanded, setExpanded] = useState(false);
  const [isClipped, setIsClipped] = useState(false);
  const textRef = useRef(null);

  useEffect(() => {
    const element = textRef.current;
    if (!element) return;
    setIsClipped(element.scrollHeight > element.clientHeight + 1);
  }, [text]);

  return (
    <div className={className}>
      <div className="relative">
        <p
          ref={textRef}
          className={`whitespace-pre-wrap ${textClassName} ${expanded ? "" : "line-clamp-3"}`}
        >
          {text}
        </p>
        {!expanded && isClipped && (
          <div
            aria-hidden="true"
            className={`pointer-events-none absolute inset-x-0 bottom-0 h-5 bg-gradient-to-t ${fadeFromClassName} to-transparent`}
          />
        )}
      </div>
      {isClipped && (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="mt-1 rounded text-[11px] font-medium text-accent-700 hover:text-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-500"
        >
          {expanded ? "Show less" : "Read more"}
        </button>
      )}
    </div>
  );
}

export default ExpandableText;
