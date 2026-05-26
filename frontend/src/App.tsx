import { Navigate, Route, Routes } from 'react-router-dom';
import type { ReactNode } from 'react';
import { AppShell } from './components/AppShell';
import { getToken } from './lib/api';
import AuthPage from './pages/AuthPage';
import ChatPage from './pages/ChatPage';
import ContentPlanPage from './pages/ContentPlanPage';
import ContentPlansPage from './pages/ContentPlansPage';
import DashboardPage from './pages/DashboardPage';
import GeneratedPostsPage from './pages/GeneratedPostsPage';
import HistoryPage from './pages/HistoryPage';
import LandingPage from './pages/LandingPage';
import OnboardingPage from './pages/OnboardingPage';
import ProfileAnalyticsPage from './pages/ProfileAnalyticsPage';
import ProfilePage from './pages/ProfilePage';
import SocialAnalyticsPage from './pages/SocialAnalyticsPage';
import ContentPlanAnalyticsPage from './pages/ContentPlanAnalyticsPage';

function Protected({ children }: { children: ReactNode }) {
  return getToken() ? <>{children}</> : <Navigate to="/auth?reason=UNAUTHORIZED" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route
        element={
          <Protected>
            <AppShell />
          </Protected>
        }
      >
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/analytics/profile" element={<ProfileAnalyticsPage />} />
        <Route path="/analytics/social" element={<SocialAnalyticsPage />} />
        <Route path="/content-plans" element={<ContentPlansPage />} />
        <Route path="/content-plans/:planId" element={<ContentPlanPage />} />
        <Route path="/content-plans/:planId/analytics" element={<ContentPlanAnalyticsPage />} />
        <Route path="/generated-posts" element={<GeneratedPostsPage />} />
      </Route>
    </Routes>
  );
}
