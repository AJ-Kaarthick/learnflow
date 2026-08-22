import AppShell from "./components/AppShell";
import ChatPage from "./pages/ChatPage";
import HomePage from "./pages/HomePage";
import StudyPage from "./pages/StudyPage";
import { ROUTES, useHashRoute } from "./router/useHashRoute";

// V2.4 Milestone 1: LearnFlow's first top-level route switch. This is
// deliberately all this file does — each page below owns its own
// state, its own layout, and its own persistence (see StudyPage.jsx
// and ChatPage.jsx) — so it stays a plain three-way switch rather
// than growing into the kind of giant conditional component the
// milestone brief warns against. Adding Recall/Revision/Settings
// later is one more line here plus one more page component, not a
// restructuring of this one.
function App() {
  const route = useHashRoute();

  return (
    <AppShell route={route}>
      {route === ROUTES.STUDY && <StudyPage />}
      {route === ROUTES.CHAT && <ChatPage />}
      {route === ROUTES.HOME && <HomePage />}
    </AppShell>
  );
}

export default App;
