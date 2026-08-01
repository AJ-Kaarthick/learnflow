import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { PersonalizationProvider } from "./context/PersonalizationContext.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <PersonalizationProvider>
      <App />
    </PersonalizationProvider>
  </StrictMode>
);
