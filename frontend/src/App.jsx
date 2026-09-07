import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import RequireAuth from './components/RequireAuth'
import RedirectIfAuthed from './components/RedirectIfAuthed'

import LoginPage from './pages/auth/LoginPage'
import RegisterPage from './pages/auth/RegisterPage'
import ForgotPasswordPage from './pages/auth/ForgotPasswordPage'
import OnboardingPage from './pages/onboarding/OnboardingPage'

import OverviewPage from './pages/OverviewPage'
import RadarPage from './pages/RadarPage'
import FlocksPage from './pages/FlocksPage'
import HousesPage from './pages/HousesPage'
import HouseDetailPage from './pages/HouseDetailPage'
import FlockChecksListPage from './pages/FlockChecksListPage'
import FlockCheckPage from './pages/FlockCheckPage'
import FlockCheckDetailPage from './pages/FlockCheckDetailPage'
import AlertsPage from './pages/AlertsPage'
import AnalyticsPage from './pages/AnalyticsPage'
import AskFlockGuardPage from './pages/AskFlockGuardPage'
import SettingsPage from './pages/SettingsPage'
import TeamPage from './pages/TeamPage'
import BillingPage from './pages/BillingPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<RedirectIfAuthed />}>
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
          <Route path="forgot-password" element={<ForgotPasswordPage />} />
        </Route>

        <Route element={<RequireAuth />}>
          <Route path="onboarding" element={<OnboardingPage />} />

          <Route element={<AppLayout />}>
            <Route index element={<OverviewPage />} />
            <Route path="radar" element={<RadarPage />} />
            <Route path="flocks" element={<FlocksPage />} />
            <Route path="houses" element={<HousesPage />} />
            <Route path="houses/:houseId" element={<HouseDetailPage />} />
            <Route path="checks" element={<FlockChecksListPage />} />
            <Route path="checks/new" element={<FlockCheckPage />} />
            <Route path="houses/:houseId/checks/:checkId" element={<FlockCheckDetailPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="ask" element={<AskFlockGuardPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="team" element={<TeamPage />} />
            <Route path="billing" element={<BillingPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
