import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { AuthProvider } from "./context/AuthContext.jsx";
import { PersonalizationProvider } from "./context/PersonalizationContext.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <PersonalizationProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </PersonalizationProvider>
  </StrictMode>
);
