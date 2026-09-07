import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock } from 'lucide-react'
import AuthShell, { IconField } from '../../components/AuthShell'
import { registerWithEmail } from '../../lib/firebase'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }
    setIsSubmitting(true)
    try {
      await registerWithEmail(email, password)
      navigate('/onboarding', { replace: true })
    } catch (err) {
      setError(
        err.code === 'auth/email-already-in-use'
          ? 'That email is already registered - try signing in instead.'
          : 'Could not create your account. Please try again.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Start monitoring"
      subtitle="Know before it becomes a problem."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-bold text-navy">
            Sign in
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
            placeholder="At least 6 characters"
          />
        </div>

        {error ? <p className="text-sm text-critical">{error}</p> : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-lg bg-forest py-3 text-sm font-bold text-white transition-colors hover:bg-forest-dark disabled:opacity-60"
        >
          {isSubmitting ? 'Creating account...' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}
