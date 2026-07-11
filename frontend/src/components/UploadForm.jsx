import { useState } from "react";
import { uploadDocument } from "../api/documents";

function UploadForm({ onUploadComplete }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | uploading | error
  const [errorMessage, setErrorMessage] = useState("");

  function handleFileChange(event) {
    setSelectedFile(event.target.files[0] || null);
    setStatus("idle");
    setErrorMessage("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!selectedFile) return;

    setStatus("uploading");
    try {
      const document = await uploadDocument(selectedFile);
      setStatus("idle");
      setSelectedFile(null);
      onUploadComplete(document);
    } catch (error) {
      setStatus("error");
      setErrorMessage(error.message);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <input
        type="file"
        accept="application/pdf"
        onChange={handleFileChange}
        className="block w-full text-sm text-slate-600 file:mr-4 file:rounded-md file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white file:cursor-pointer cursor-pointer"
      />
      <button
        type="submit"
        disabled={!selectedFile || status === "uploading"}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        {status === "uploading" ? "Uploading..." : "Upload PDF"}
      </button>
      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}
    </form>
  );
}

export default UploadForm;
