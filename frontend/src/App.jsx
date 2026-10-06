import AppShell from "./components/AppShell";
import ChatPage from "./pages/ChatPage";
import HomePage from "./pages/HomePage";
import RevisionPage from "./pages/RevisionPage";
import StudyPage from "./pages/StudyPage";
import { ROUTES, useHashRoute } from "./router/useHashRoute";

// V2.4 Milestone 1: LearnFlow's top-level route switch. Each page owns
// its own state and layout.
function App() {
  const route = useHashRoute();

  return (
    <AppShell route={route}>
      {route === ROUTES.STUDY && <StudyPage />}
      {route === ROUTES.CHAT && <ChatPage />}
      {route === ROUTES.REVISION && <RevisionPage />}
      {route === ROUTES.HOME && <HomePage />}
    </AppShell>
  );
}

export default App;
