import LogoMark from './Logo'

// The single branded full-page loading state - one centered, gently
// breathing logo, never a spinner scattered per-section. Used wherever the
// app needs a whole-screen "not ready yet" state (auth check, farm
// bootstrap) - not for small inline loads, which should use their own
// lightweight indicator instead of this.
export default function LoadingScreen({ label = 'Loading...' }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg">
      <LogoMark size={56} className="[animation:logo-breathe_1.8s_ease-in-out_infinite]" />
      <p className="text-sm text-secondary">{label}</p>
    </div>
  )
}
