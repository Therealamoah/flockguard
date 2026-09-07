import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Mail, MailCheck } from 'lucide-react'
import AuthShell, { IconField } from '../../components/AuthShell'
import { resetPassword } from '../../lib/firebase'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      await resetPassword(email)
      setSent(true)
    } catch {
      setError('Could not send reset email. Check the address and try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Reset password"
      footer={
        <Link to="/login" className="font-bold text-navy">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <div className="flex flex-col items-center gap-3 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-normal/10 text-normal">
            <MailCheck size={22} />
          </span>
          <p className="text-sm text-navy/70">
            If an account exists for <strong>{email}</strong>, a reset link is on its way.
          </p>
        </div>
      ) : (
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
          {error ? <p className="text-sm text-critical">{error}</p> : null}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-lg bg-forest py-3 text-sm font-bold text-white transition-colors hover:bg-forest-dark disabled:opacity-60"
          >
            {isSubmitting ? 'Sending...' : 'Send reset link'}
          </button>
        </form>
      )}
    </AuthShell>
  )
}
