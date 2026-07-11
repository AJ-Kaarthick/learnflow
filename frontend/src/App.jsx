import { useEffect, useState } from "react";
import { getHealth } from "./api/client";

function App() {
  // "checking" | "connected" | "error" — three states the UI can be in.
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    getHealth()
      .then(() => setStatus("connected"))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white border border-slate-200 rounded-lg p-8">
        <h1 className="text-2xl font-semibold text-slate-900">LearnFlow</h1>
        <p className="mt-1 text-sm text-slate-500">
          Milestone 0 &mdash; frontend/backend connectivity check
        </p>

        <div className="mt-6 flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              status === "connected"
                ? "bg-emerald-500"
                : status === "error"
                ? "bg-red-500"
                : "bg-amber-400"
            }`}
          />
          <span className="text-sm text-slate-700">
            {status === "checking" && "Checking backend..."}
            {status === "connected" && "Backend is connected"}
            {status === "error" &&
              "Could not reach the backend. Is it running on port 8000?"}
          </span>
        </div>
      </div>
    </main>
  );
}

export default App;
