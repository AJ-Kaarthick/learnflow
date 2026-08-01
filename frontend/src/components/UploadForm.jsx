import { useRef, useState } from "react";
import { uploadDocument } from "../api/documents";

// Mirrors the backend's own rules and wording exactly (see
// ALLOWED_CONTENT_TYPE / MAX_FILE_SIZE_BYTES in routes_documents.py).
// This is a fast-feedback layer in front of that check, not a
// replacement for it — the backend still validates every upload.
const ALLOWED_CONTENT_TYPE = "application/pdf";
const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

function validateFile(file) {
  if (file.type !== ALLOWED_CONTENT_TYPE) {
    return "Only PDF files are accepted.";
  }
  if (file.size === 0) {
    return "Uploaded file is empty.";
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "File exceeds the 20 MB limit.";
  }
  return null;
}

function UploadForm({ onUploadComplete }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | uploading | error
  const [errorMessage, setErrorMessage] = useState("");

  // Lets us reset the native input after a successful upload, so
  // selecting the exact same file again later still fires a change
  // event (browsers don't fire one if the input's value hasn't
  // changed since the last selection).
  const fileInputRef = useRef(null);

  function handleFileChange(event) {
    const file = event.target.files[0] || null;
    setStatus("idle");
    setErrorMessage("");

    if (!file) {
      setSelectedFile(null);
      return;
    }

    const validationError = validateFile(file);
    if (validationError) {
      // Deliberately not clearing the native input here: leaving the
      // rejected filename visible helps the student see what they
      // picked and why it didn't work.
      setSelectedFile(null);
      setStatus("error");
      setErrorMessage(validationError);
      return;
    }

    setSelectedFile(file);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!selectedFile) return;

    setStatus("uploading");
    setErrorMessage("");
    try {
      const document = await uploadDocument(selectedFile);
      setStatus("idle");
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      onUploadComplete(document);
    } catch (error) {
      setStatus("error");
      setErrorMessage(error.message);
    }
  }

  const isUploading = status === "uploading";

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label htmlFor="pdf-upload" className="block text-sm font-medium text-slate-700">
        Choose a PDF
      </label>
      <input
        id="pdf-upload"
        type="file"
        accept="application/pdf"
        onChange={handleFileChange}
        disabled={isUploading}
        ref={fileInputRef}
        className="block w-full text-sm text-slate-600 file:mr-4 file:cursor-pointer file:rounded-md file:border file:border-slate-300 file:bg-surface file:px-4 file:py-2 file:text-sm file:font-medium file:text-slate-700 file:transition-colors hover:file:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40"
      />
      <button
        type="submit"
        disabled={!selectedFile || isUploading}
        className="inline-flex items-center gap-2 rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:opacity-40"
      >
        {isUploading && (
          <span
            className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white"
            aria-hidden="true"
          />
        )}
        {isUploading ? "Uploading..." : "Upload PDF"}
      </button>
      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}
    </form>
  );
}

export default UploadForm;
