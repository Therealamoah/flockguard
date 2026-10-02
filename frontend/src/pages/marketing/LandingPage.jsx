import { Link } from 'react-router-dom'
import {
  Radar as RadarIcon,
  ShieldAlert,
  Sparkles,
  Users,
  ClipboardList,
  BarChart3,
  ArrowRight,
  Sun,
  Moon,
} from 'lucide-react'
import LogoMark from '../../components/Logo'
import { useThemeStore } from '../../store/useThemeStore'

const FEATURES = [
  {
    Icon: ClipboardList,
    title: 'Morning & evening flock checks',
    body: 'Record dead birds, feed, water and how the birds look in seconds - or just say it out loud. FlockGuard compares it with how that house usually does.',
  },
  {
    Icon: RadarIcon,
    title: 'A clear risk number',
    body: 'Every check gets a risk number from 0 to 100, with the reasons in plain words - so you know which house to check first and why.',
  },
  {
    Icon: ShieldAlert,
    title: 'Warnings without the noise',
    body: 'One warning per house, not ten. It clears by itself when the birds are back to normal, or when you record what you found.',
  },
  {
    Icon: Sparkles,
    title: 'Ask FlockGuard',
    body: 'Ask questions in simple English and get answers from your own farm records and trusted poultry guides. It never makes up numbers and never names a disease.',
  },
  {
    Icon: Users,
    title: 'Built for a team',
    body: 'Owners, managers and farm workers each get their own login and access, so everyone sees what they need.',
  },
  {
    Icon: BarChart3,
    title: 'Trends you can act on',
    body: 'Compare houses and see dead birds, feed and water over time, so you catch problems before they get big.',
  },
]

const STEPS = [
  { n: '01', title: 'Log a check', body: 'A worker does the morning or evening check on their phone.' },
  { n: '02', title: 'FlockGuard gives it a risk number', body: 'It is compared with how that house usually does, and gets a number from 0 to 100 straight away.' },
  { n: '03', title: 'You get warned, with reasons', body: 'If something is wrong, you get a warning and the AI explains in simple words what changed and why.' },
]

export default function LandingPage() {
  const { theme, toggleTheme } = useThemeStore()

  return (
    <div className="bg-bg">
      {/* Hero */}
      <div className="relative overflow-hidden bg-forest-dark">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: "url('/hero-bg.png')" }}
          aria-hidden="true"
        />
        {/* Dark forest gradient over the photo - the source image is bright
        on its right edge (windows/foliage), which would fight the white
        headline text without this. */}
        <div className="absolute inset-0 bg-linear-to-br from-forest-dark/95 via-forest-dark/85 to-forest-dark/70" />

        <div className="relative">
        <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-2">
            <LogoMark size={32} />
            <span className="font-display text-xl font-extrabold text-white">FlockGuard</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className="rounded-full p-2 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
              title="Toggle theme"
            >
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <Link to="/login" className="text-sm font-semibold text-white/80 hover:text-white">
              Log in
            </Link>
            <Link
              to="/register"
              className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-forest-dark shadow-sm transition-transform hover:scale-[1.02]"
            >
              Get Started
            </Link>
          </div>
        </nav>

        <div className="mx-auto max-w-4xl px-6 pb-20 pt-10 text-center sm:pt-16">
          <h1 className="font-display text-4xl font-extrabold leading-tight text-white sm:text-5xl">
            Know a flock is in trouble before it's a crisis.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-white/80 sm:text-lg">
            FlockGuard warns poultry farmers early when birds start getting sick. Do a quick check each morning
            and evening, and FlockGuard tells you which house needs you first - and explains why in simple words.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/register"
              className="flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-forest-dark shadow-lg transition-transform hover:scale-[1.02]"
            >
              Get Started Free
              <ArrowRight size={16} />
            </Link>
            <Link
              to="/login"
              className="rounded-full border border-white/30 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
            >
              Log In
            </Link>
          </div>
        </div>
        </div>
      </div>

      {/* Features */}
      <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-2xl font-extrabold text-navy sm:text-3xl">
            Everything a working farmer actually needs
          </h2>
          <p className="mt-3 text-secondary">No noise, no black-box scores, no guessing what changed overnight.</p>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ Icon, title, body }) => (
            <div key={title} className="rounded-2xl border border-hairline bg-surface p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-forest/10">
                <Icon size={20} className="text-forest" />
              </div>
              <h3 className="mt-4 font-display text-base font-bold text-navy">{title}</h3>
              <p className="mt-2 text-sm text-secondary">{body}</p>
            </div>
          ))}
        </div>
      </div>

      {/* How it works */}
      <div className="border-y border-hairline bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <h2 className="text-center font-display text-2xl font-extrabold text-navy sm:text-3xl">How it works</h2>
          <div className="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-3">
            {STEPS.map(({ n, title, body }) => (
              <div key={n}>
                <span className="font-display text-3xl font-extrabold text-forest/30">{n}</span>
                <h3 className="mt-2 font-display text-base font-bold text-navy">{title}</h3>
                <p className="mt-2 text-sm text-secondary">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Final CTA */}
      <div
        className="relative bg-forest-dark bg-cover bg-center"
        style={{ backgroundImage: "url('/herro-bg.png')" }}
      >
        <div className="absolute inset-0 bg-forest-dark/40" />
        <div className="relative mx-auto max-w-3xl px-6 py-16 text-center sm:py-20">
          <h2 className="font-display text-2xl font-extrabold text-white sm:text-3xl">
            Set up your first house in a few minutes.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-white/80">
            Free to get started. No payment details required.
          </p>
          <Link
            to="/register"
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-forest-dark shadow-lg transition-transform hover:scale-[1.02]"
          >
            Get Started Free
            <ArrowRight size={16} />
          </Link>
        </div>
      </div>

      <footer className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-8 text-xs text-muted sm:flex-row">
        <div className="flex items-center gap-2">
          <LogoMark size={20} />
          <span className="font-semibold text-secondary">FlockGuard</span>
        </div>
        <p>&copy; {new Date().getFullYear()} FlockGuard. All rights reserved.</p>
      </footer>
    </div>
  )
}
