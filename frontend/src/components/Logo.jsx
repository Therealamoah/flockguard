import { useState } from 'react'

// Icon-only crop of the FlockGuard mark (shield + bird, no wordmark) so it
// stays legible at small sizes - falls back to a flat, modern mark until then.
export default function LogoMark({ size = 32, className = '' }) {
  const [imageFailed, setImageFailed] = useState(false)

  if (!imageFailed) {
    return (
      <img
        src="/logo-mark.png"
        alt="FlockGuard"
        width={size}
        height={size}
        className={className}
        onError={() => setImageFailed(true)}
      />
    )
  }

  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className}>
      <rect width="32" height="32" rx="8" fill="#1B4332" />
      <path
        d="M10 20.5c0-3.6 2.7-6.5 6-6.5s6 2.9 6 6.5"
        fill="none"
        stroke="#F6F5F1"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="16" cy="11.5" r="3.2" fill="#F6F5F1" />
      <path d="M18.8 9.4 21 8l-.6 2.5-1.6-1.1z" fill="#2F9E58" />
    </svg>
  )
}
