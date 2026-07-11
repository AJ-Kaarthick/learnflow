import { useEffect, useState } from "react";
import { getHealth } from "../api/health";

function BackendStatus() {
  const [status, setStatus] = useState("checking"); // checking | connected | error

  useEffect(() => {
    getHealth()
      .then(() => setStatus("connected"))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div className="flex items-center gap-2">
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
        {status === "error" && "Could not reach the backend. Is it running on port 8000?"}
      </span>
    </div>
  );
}

export default BackendStatus;
