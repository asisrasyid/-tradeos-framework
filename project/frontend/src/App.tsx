import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AppLayout from './components/layout/AppLayout'
import Live from './pages/Live'
import Theories from './pages/Theories'
import TheoryBuilder from './pages/TheoryBuilder'
import Patterns from './pages/Patterns'
import Backtest from './pages/Backtest'
import TradeLog from './pages/TradeLog'
import HMMModels from './pages/HMMModels'
import Login from './pages/Login'
import TheoryDetail from './pages/TheoryDetail'
import MT5Terminal from './pages/MT5Terminal'
import { useAuthStore } from './store/authStore'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(s => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />

          {/* Protected */}
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Live />} />
            <Route path="theories" element={<Theories />} />
            <Route path="theories/:id" element={<TheoryDetail />} />
            <Route path="builder" element={<TheoryBuilder />} />
            <Route path="patterns" element={<Patterns />} />
            <Route path="backtest" element={<Backtest />} />
            <Route path="trades" element={<TradeLog />} />
            <Route path="hmm" element={<HMMModels />} />
            <Route path="mt5" element={<MT5Terminal />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
