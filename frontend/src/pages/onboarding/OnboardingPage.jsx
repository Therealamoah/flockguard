import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Sprout, Warehouse, Bird, CheckCircle2 } from 'lucide-react'
import { api } from '../../lib/api'
import { useAppStore } from '../../store/useAppStore'

const TOTAL_STEPS = 4
const STEP_ICON = { 1: Sprout, 2: Warehouse, 3: Bird }

function Stepper({ step }) {
  return (
    <div className="flex items-center justify-center gap-2 border-b border-hairline bg-surface py-6">
      {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1).map((n, i) => (
        <div key={n} className="flex items-center gap-2">
          <div
            className={[
              'flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold',
              n < step
                ? 'bg-forest text-white'
                : n === step
                  ? 'bg-forest-dark text-white'
                  : 'bg-hairline text-navy/50',
            ].join(' ')}
          >
            {n < step ? <Check size={16} /> : n}
          </div>
          {i < TOTAL_STEPS - 1 ? <div className="h-px w-10 bg-hairline" /> : null}
        </div>
      ))}
    </div>
  )
}

export default function OnboardingPage() {
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [farmName, setFarmName] = useState('')
  const [farmId, setFarmId] = useState(null)

  const [houseName, setHouseName] = useState('')
  const [birdCapacity, setBirdCapacity] = useState('')
  const [houseId, setHouseId] = useState(null)

  const [birdType, setBirdType] = useState('broiler')
  const [breed, setBreed] = useState('')
  const [initialBirdCount, setInitialBirdCount] = useState('')
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10))

  const bootstrap = useAppStore((s) => s.bootstrap)
  const navigate = useNavigate()

  async function handleCreateFarm(e) {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const farm = await api.farms.create({ name: farmName })
      setFarmId(farm.id)
      setStep(2)
    } catch {
      setError('Could not create your farm. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleCreateHouse(e) {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const house = await api.houses.create(farmId, {
        name: houseName,
        bird_capacity: birdCapacity ? Number(birdCapacity) : null,
      })
      setHouseId(house.id)
      setStep(3)
    } catch {
      setError('Could not create the house. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleCreateFlock(e) {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      await api.flocks.create(farmId, houseId, {
        bird_type: birdType,
        breed,
        start_date: startDate,
        initial_bird_count: Number(initialBirdCount),
      })
      setStep(4)
    } catch {
      setError('Could not add the flock. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleFinish() {
    await bootstrap()
    navigate('/', { replace: true })
  }

  const StepIcon = STEP_ICON[step]

  return (
    <div className="min-h-screen bg-bg">
      <Stepper step={step} />

      <div className="mx-auto max-w-xl px-4 py-16">
        <div className="rounded-2xl border border-hairline bg-surface p-8 shadow-sm">
          {step === 1 ? (
            <form onSubmit={handleCreateFarm}>
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
                  <StepIcon size={20} />
                </span>
                <p className="text-xs font-bold uppercase tracking-wide text-forest">Step 1 of 3</p>
              </div>
              <h1 className="mt-3 font-display text-3xl font-extrabold text-navy">Create your farm</h1>
              <p className="mt-2 text-sm text-navy/60">This is where all your houses and flocks will live.</p>

              <label className="mt-6 mb-1 block text-sm font-semibold text-navy">Farm name</label>
              <input
                required
                value={farmName}
                onChange={(e) => setFarmName(e.target.value)}
                placeholder="e.g. Collins Poultry Farm"
                className="w-full rounded-lg border border-hairline px-3 py-2.5 text-sm outline-none focus:border-forest"
              />

              {error ? <p className="mt-3 text-sm text-critical">{error}</p> : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="mt-6 rounded-lg bg-forest px-6 py-3 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
              >
                {isSubmitting ? 'Creating...' : 'Continue'}
              </button>
            </form>
          ) : null}

          {step === 2 ? (
            <form onSubmit={handleCreateHouse}>
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
                  <StepIcon size={20} />
                </span>
                <p className="text-xs font-bold uppercase tracking-wide text-forest">Step 2 of 3</p>
              </div>
              <h1 className="mt-3 font-display text-3xl font-extrabold text-navy">
                Set up your first poultry house
              </h1>
              <p className="mt-2 text-sm text-navy/60">Each house tracks its own risk and flock history.</p>

              <label className="mt-6 mb-1 block text-sm font-semibold text-navy">House name</label>
              <input
                required
                value={houseName}
                onChange={(e) => setHouseName(e.target.value)}
                placeholder="House A"
                className="w-full rounded-lg border border-hairline px-3 py-2.5 text-sm outline-none focus:border-forest"
              />

              <label className="mt-4 mb-1 block text-sm font-semibold text-navy">Capacity (birds)</label>
              <input
                type="number"
                min="1"
                value={birdCapacity}
                onChange={(e) => setBirdCapacity(e.target.value)}
                placeholder="1500"
                className="w-full rounded-lg border border-hairline px-3 py-2.5 text-sm outline-none focus:border-forest"
              />

              {error ? <p className="mt-3 text-sm text-critical">{error}</p> : null}

              <div className="mt-6 flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="rounded-lg border border-hairline px-6 py-3 text-sm font-bold text-navy hover:bg-forest/5"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-lg bg-forest px-6 py-3 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
                >
                  {isSubmitting ? 'Creating...' : 'Continue'}
                </button>
              </div>
            </form>
          ) : null}

          {step === 3 ? (
            <form onSubmit={handleCreateFlock}>
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
                  <StepIcon size={20} />
                </span>
                <p className="text-xs font-bold uppercase tracking-wide text-forest">Step 3 of 3</p>
              </div>
              <h1 className="mt-3 font-display text-3xl font-extrabold text-navy">Add your first flock</h1>
              <p className="mt-2 text-sm text-navy/60">Tell us what's currently living in this house.</p>

              <label className="mt-6 mb-1 block text-sm font-semibold text-navy">Bird type</label>
              <div className="flex gap-2">
                {['broiler', 'layer', 'breeder'].map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setBirdType(type)}
                    className={[
                      'flex-1 rounded-lg border px-3 py-2 text-sm font-medium capitalize transition-colors',
                      birdType === type
                        ? 'border-forest bg-forest/10 text-forest'
                        : 'border-hairline text-navy/70 hover:bg-forest/5',
                    ].join(' ')}
                  >
                    {type}
                  </button>
                ))}
              </div>

              <label className="mt-4 mb-1 block text-sm font-semibold text-navy">Breed</label>
              <input
                required
                value={breed}
                onChange={(e) => setBreed(e.target.value)}
                placeholder="Cobb 500"
                className="w-full rounded-lg border border-hairline px-3 py-2.5 text-sm outline-none focus:border-forest"
              />

              <div className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-semibold text-navy">Birds placed</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={initialBirdCount}
                    onChange={(e) => setInitialBirdCount(e.target.value)}
                    placeholder="1500"
                    className="w-full rounded-lg border border-hairline px-3 py-2.5 text-sm outline-none focus:border-forest"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-navy">Placement date</label>
                  <input
                    type="date"
                    required
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full rounded-lg border border-hairline px-3 py-2.5 text-sm outline-none focus:border-forest"
                  />
                </div>
              </div>

              {error ? <p className="mt-3 text-sm text-critical">{error}</p> : null}

              <div className="mt-6 flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="rounded-lg border border-hairline px-6 py-3 text-sm font-bold text-navy hover:bg-forest/5"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-lg bg-forest px-6 py-3 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
                >
                  {isSubmitting ? 'Finishing...' : 'Finish Setup'}
                </button>
              </div>
            </form>
          ) : null}

          {step === 4 ? (
            <div className="text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-normal/10 text-normal">
                <CheckCircle2 size={32} />
              </div>
              <h1 className="mt-4 font-display text-3xl font-extrabold text-navy">Your farm is ready.</h1>
              <p className="mt-2 text-sm text-navy/60">
                {farmName}, {houseName} and your first flock are all set up.
              </p>
              <button
                onClick={handleFinish}
                className="mt-6 rounded-lg bg-forest px-6 py-3 text-sm font-bold text-white hover:bg-forest-dark"
              >
                Go to Dashboard
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
