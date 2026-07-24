/**
 * Triggers a browser download for text content by creating a temporary
 * object URL and clicking a hidden anchor. This is the same mechanism
 * the Summary panel originally used inline; it now lives here so every
 * panel's export button shares one implementation instead of each
 * re-implementing the Blob/anchor dance.
 */
export function downloadTextFile(filename, content, mimeType = "text/markdown") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
