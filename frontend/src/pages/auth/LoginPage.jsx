import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Mail, Lock } from 'lucide-react'
import AuthShell, { IconField } from '../../components/AuthShell'
import { loginWithEmail } from '../../lib/firebase'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      await loginWithEmail(email, password)
      navigate(location.state?.from?.pathname || '/', { replace: true })
    } catch {
      setError('Could not sign in. Check your email and password.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to check on your farm."
      footer={
        <>
          Don't have an account?{' '}
          <Link to="/register" className="font-bold text-navy">
            Start Monitoring
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div>
          <label className="mb-1 block text-sm font-semibold text-navy">Email address</label>
          <IconField
            icon={Mail}
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@farm.com"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-semibold text-navy">Password</label>
          <IconField
            icon={Lock}
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
        </div>

        {error ? <p className="text-sm text-critical">{error}</p> : null}

        <div className="flex items-center justify-between text-sm">
          <label className="flex items-center gap-2 text-navy/70">
            <input type="checkbox" className="h-4 w-4 accent-forest" />
            Remember me
          </label>
          <Link to="/forgot-password" className="font-semibold text-navy">
            Forgot password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-lg bg-forest py-3 text-sm font-bold text-white transition-colors hover:bg-forest-dark disabled:opacity-60"
        >
          {isSubmitting ? 'Signing in...' : 'Sign In'}
        </button>
      </form>
    </AuthShell>
  )
}
