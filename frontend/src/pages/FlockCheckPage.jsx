import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import NumberStepper from '../components/NumberStepper'
import StatusBadge from '../components/StatusBadge'
import { statusMeta } from '../lib/risk'
import { inspectionPriorities } from '../lib/riskFactors'
import {
  Camera,
  Upload,
  Mic,
  LineChart,
  Wheat,
  Droplets,
  ClipboardList,
  Users,
  Sparkles,
  Warehouse,
  Sun,
  Moon,
  Siren,
  Stethoscope,
  Loader2,
  MessageCircle,
  Building2,
  Activity,
  Thermometer,
  StickyNote,
} from 'lucide-react'

const BASELINE_SAMPLE_SIZE = 14 // mirrors backend/app/risk_engine/engine.py

function IconChip({ Icon }) {
  return (
    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-hairline/70 text-navy/60">
      <Icon size={14} />
    </span>
  )
}

function SectionCard({ icon: Icon, title, hint, children }) {
  return (
    <section className="rounded-xl border border-hairline bg-surface p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest/10 text-forest">
          <Icon size={14} />
        </span>
        <h2 className="text-sm font-bold uppercase tracking-wide text-forest">{title}</h2>
      </div>
      {hint ? <p className="mt-1 text-xs text-navy/50">{hint}</p> : null}
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  )
}

const WATER_OPTIONS = ['normal', 'lower', 'higher']
const ACTIVITY_OPTIONS = ['normal', 'reduced', 'lethargic']
const FEEDING_OPTIONS = ['normal', 'reduced', 'none']
const ROUTINE_PERIODS = ['morning', 'evening']

function ToggleRow({ label, options, value, onChange }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-semibold text-navy">{label}</label>
      <div className="flex gap-2">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            className={[
              'flex-1 rounded-lg border px-3 py-2 text-sm font-medium capitalize transition-colors',
              value === opt
                ? 'border-forest bg-forest/10 text-forest'
                : 'border-hairline text-navy/70 hover:bg-forest/5',
            ].join(' ')}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}

function average(values) {
  const clean = values.filter((v) => v != null)
  return clean.length ? clean.reduce((a, b) => a + b, 0) / clean.length : null
}

function baselineWindowLabel(sample) {
  if (sample.length < 2) return 'recent'
  const newest = new Date(sample[0].recorded_at)
  const oldest = new Date(sample[sample.length - 1].recorded_at)
  const days = Math.max(1, Math.round((newest - oldest) / 86400000))
  return `${days}-day`
}

function computeBaseline(priorChecks) {
  const sample = priorChecks.slice(0, BASELINE_SAMPLE_SIZE)
  return {
    windowLabel: baselineWindowLabel(sample),
    avgMortality: average(sample.map((c) => c.mortality)),
    avgFeed: average(sample.map((c) => c.feed_kg)),
  }
}

function describeChanges(
  { mortality, sickOrInjured, feedKg, waterLiters, activity, feedingBehaviour, crowding, unusualSound },
  priorChecks,
  houseName
) {
  const prior = priorChecks[0] || null
  const baseline = computeBaseline(priorChecks)
  const changes = []

  // Mortality
  let headline
  if (prior) {
    if (mortality > prior.mortality) headline = `Mortality up from ${prior.mortality} to ${mortality}`
    else if (mortality < prior.mortality) headline = `Mortality down from ${prior.mortality} to ${mortality}`
    else headline = `Mortality unchanged at ${mortality}`
  } else {
    headline = `Mortality recorded at ${mortality} (first check for this house)`
  }
  let detail = 'No baseline yet for this house.'
  if (baseline.avgMortality != null) {
    const ratio = baseline.avgMortality > 0 ? mortality / baseline.avgMortality : mortality > 0 ? Infinity : 1
    const qualifier = ratio <= 1.1 ? 'In line with' : ratio < 1.5 ? 'Slightly above' : ratio < 2.5 ? 'Above' : 'Well above'
    detail = `${qualifier} ${houseName || 'this house'}'s ${baseline.windowLabel} average.`
  }
  changes.push({ Icon: LineChart, headline, detail })

  // Feed
  if (feedKg !== '' && feedKg !== null) {
    let feedHeadline
    let feedDetail
    if (baseline.avgFeed != null) {
      const diff = feedKg - baseline.avgFeed
      feedHeadline =
        Math.abs(diff) < baseline.avgFeed * 0.03
          ? 'Feed intake steady'
          : diff < 0
            ? 'Feed intake trending down'
            : 'Feed intake trending up'
      feedDetail = `${feedKg}kg logged today vs. ~${Math.round(baseline.avgFeed)}kg average.`
    } else {
      feedHeadline = 'Feed intake logged'
      feedDetail = `${feedKg}kg (first reading for this house).`
    }
    changes.push({ Icon: Wheat, headline: feedHeadline, detail: feedDetail })
  }

  // Water (optional)
  if (waterLiters !== '' && waterLiters !== null && prior?.water_liters != null) {
    const diff = waterLiters - prior.water_liters
    if (diff !== 0) {
      changes.push({
        Icon: Droplets,
        headline: `Water intake ${diff > 0 ? 'up' : 'down'} from ${prior.water_liters}L to ${waterLiters}L`,
        detail: 'Compared with the most recent check.',
      })
    }
  }

  // Behaviour
  const behaviourFlags = []
  if (activity !== 'normal') behaviourFlags.push(`activity ${activity}`)
  if (feedingBehaviour !== 'normal') behaviourFlags.push(`feeding ${feedingBehaviour}`)
  if (crowding) behaviourFlags.push('crowding observed')
  if (unusualSound) behaviourFlags.push('unusual noise observed')
  if (sickOrInjured > 0) behaviourFlags.push(`${sickOrInjured} sick/injured`)

  changes.push({
    Icon: ClipboardList,
    headline: behaviourFlags.length > 0 ? `Behaviour flagged: ${behaviourFlags.join(', ')}` : 'Behaviour flagged: normal',
    detail: 'Recorded during this check.',
  })

  return changes
}

export default function FlockCheckPage() {
  const { currentFarmId, currentHouseId, houses } = useAppStore()
  const navigate = useNavigate()
  const house = houses.find((h) => h.id === currentHouseId)

  const [period, setPeriod] = useState(() => (new Date().getHours() < 15 ? 'morning' : 'evening'))
  const [birdCount, setBirdCount] = useState('')
  const [mortality, setMortality] = useState(0)
  const [sickOrInjured, setSickOrInjured] = useState(0)
  const [feedKg, setFeedKg] = useState('')
  const [waterLevel, setWaterLevel] = useState('normal')
  const [waterLiters, setWaterLiters] = useState('')
  const [activity, setActivity] = useState('normal')
  const [feedingBehaviour, setFeedingBehaviour] = useState('normal')
  const [crowding, setCrowding] = useState(false)
  const [unusualSound, setUnusualSound] = useState(false)
  const [temperature, setTemperature] = useState('')
  const [humidity, setHumidity] = useState('')
  const [notes, setNotes] = useState('')

  const [photo, setPhoto] = useState(null)
  const [isUploadingPhoto, setIsUploadingPhoto] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [audio, setAudio] = useState(null)
  const mediaRecorderRef = useRef(null)

  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [priorChecks, setPriorChecks] = useState([])
  const [explanation, setExplanation] = useState('')
  const [explanationLoading, setExplanationLoading] = useState(false)

  async function handlePhotoChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setIsUploadingPhoto(true)
    try {
      const uploaded = await api.media.upload(file, 'image')
      setPhoto(uploaded)
    } catch {
      setError('Photo upload failed. You can still submit without it.')
    } finally {
      setIsUploadingPhoto(false)
    }
  }

  async function toggleRecording() {
    if (isRecording) {
      mediaRecorderRef.current?.stop()
      setIsRecording(false)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const chunks = []
      recorder.ondataavailable = (e) => chunks.push(e.data)
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunks, { type: 'audio/webm' })
        const file = new File([blob], 'flock-audio.webm', { type: 'audio/webm' })
        try {
          const uploaded = await api.media.upload(file, 'video')
          setAudio(uploaded)
        } catch {
          setError('Audio upload failed. You can still submit without it.')
        }
      }
      mediaRecorderRef.current = recorder
      recorder.start()
      setIsRecording(true)
    } catch {
      setError('Could not access the microphone.')
    }
  }

  async function generateExplanation(response, house_) {
    setExplanationLoading(true)
    try {
      const factorsText = response.risk_factors.map((f) => `${f.label} (${Math.round(f.points)}%)`).join(', ')
      const { answer } = await api.ask(
        `In 2-3 sentences, explain why ${house_?.name || 'this house'} just scored a Flock Check risk of ` +
          `${response.risk_score} (${response.risk_status}). Factors detected: ${factorsText || 'none'}. ` +
          'Describe the pattern that triggered this, not a disease diagnosis.'
      )
      setExplanation(answer)
    } catch {
      setExplanation('')
    } finally {
      setExplanationLoading(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!currentHouseId) {
      setError('No house selected.')
      return
    }
    if (birdCount === '' || mortality === '') {
      setError('Bird count and mortality are required.')
      return
    }

    setIsSubmitting(true)
    try {
      const fetchedPriorChecks = await api.flockChecks.list(currentFarmId, currentHouseId)

      const response = await api.flockChecks.submit(currentFarmId, currentHouseId, {
        period,
        bird_count: Number(birdCount),
        mortality: Number(mortality),
        sick_or_injured: Number(sickOrInjured),
        feed_kg: feedKg === '' ? null : Number(feedKg),
        water_level: waterLevel,
        water_liters: waterLiters === '' ? null : Number(waterLiters),
        activity,
        feeding_behaviour: feedingBehaviour,
        crowding_observed: crowding,
        unusual_sound_observed: unusualSound,
        temperature_c: temperature === '' ? null : Number(temperature),
        humidity_pct: humidity === '' ? null : Number(humidity),
        notes: notes || null,
        photo_url: photo?.url ?? null,
        photo_public_id: photo?.public_id ?? null,
        audio_url: audio?.url ?? null,
        audio_public_id: audio?.public_id ?? null,
      })
      setResult(response)
      setPriorChecks(fetchedPriorChecks)

      if (response.risk_status !== 'normal') {
        generateExplanation(response, house)
      }
    } catch {
      setError('Could not submit this Flock Check. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (result) {
    const meta = statusMeta(result.risk_status)
    const changes = describeChanges(
      { mortality, sickOrInjured, feedKg, waterLiters, activity, feedingBehaviour, crowding, unusualSound },
      priorChecks,
      house?.name
    )
    const priorities = inspectionPriorities(result.risk_factors)

    return (
      <div className="mx-auto max-w-2xl p-6">
        <div className="overflow-hidden rounded-xl border border-hairline bg-surface shadow-sm">
          <div className="p-6 text-center" style={{ backgroundColor: `${meta.color}14` }}>
            <p className="text-xs font-bold uppercase tracking-wide text-navy/50">Flock Check complete</p>
            <div
              className="relative mx-auto mt-3 flex h-24 w-24 items-center justify-center rounded-full"
              style={{ background: `conic-gradient(${meta.color} ${result.risk_score * 3.6}deg, #E4E1D8 0deg)` }}
            >
              <div className="flex h-18 w-18 items-center justify-center rounded-full bg-surface">
                <span className="font-display text-2xl font-extrabold" style={{ color: meta.color }}>
                  {result.risk_score}
                </span>
              </div>
            </div>
            <div className="mt-3 flex justify-center">
              <StatusBadge status={result.risk_status} />
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest/10 text-forest">
              <LineChart size={14} />
            </span>
            <h2 className="text-sm font-bold text-navy">What changed</h2>
          </div>
          <ul className="mt-4 space-y-3">
            {changes.map((c, i) => (
              <li key={i} className="flex gap-3 border-b border-hairline pb-3 last:border-0 last:pb-0">
                <IconChip Icon={c.Icon} />
                <div>
                  <p className="text-sm font-semibold text-navy">{c.headline}</p>
                  <p className="text-xs text-navy/50">{c.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {result.risk_status !== 'normal' ? (
          <div className="mt-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-ai/10 text-ai">
                <Sparkles size={14} />
              </span>
              <h2 className="text-sm font-bold text-navy">Why FlockGuard flagged it</h2>
            </div>
            <p className="mt-3 flex items-center gap-2 text-sm text-navy/70">
              {explanationLoading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Generating explanation...
                </>
              ) : (
                explanation || null
              )}
            </p>
          </div>
        ) : null}

        {priorities.length > 0 ? (
          <div className="mt-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest/10 text-forest">
                <Stethoscope size={14} />
              </span>
              <h2 className="text-sm font-bold text-navy">Recommended inspection priorities</h2>
            </div>
            <ol className="mt-4 space-y-3">
              {priorities.map((p, i) => (
                <li key={p.key} className="flex gap-3">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-hairline/70 text-xs font-bold text-navy">
                    {i + 1}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-navy">{p.headline}</p>
                    <p className="text-xs text-navy/50">{p.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => navigate(`/houses/${currentHouseId}`)}
            className="flex items-center gap-1.5 rounded-lg border border-hairline px-5 py-2.5 text-sm font-bold text-navy hover:bg-forest/5"
          >
            <Building2 size={15} />
            View House
          </button>
          <button
            onClick={() => navigate('/ask')}
            className="flex items-center gap-1.5 rounded-lg border border-hairline px-5 py-2.5 text-sm font-bold text-navy hover:bg-forest/5"
          >
            <MessageCircle size={15} />
            Ask FlockGuard
          </button>
          <button
            onClick={() => navigate(`/houses/${currentHouseId}`, { state: { openInspection: true } })}
            className="flex items-center gap-1.5 rounded-lg bg-forest px-5 py-2.5 text-sm font-bold text-white hover:bg-forest-dark"
          >
            <Stethoscope size={15} />
            Record Inspection
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-xl p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
          <ClipboardList size={20} />
        </span>
        <h1 className="font-display text-2xl font-extrabold text-navy">New Flock Check</h1>
      </div>

      <div className="mt-4 flex items-center gap-3 rounded-xl border border-hairline bg-surface p-4 shadow-sm">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
          <Warehouse size={16} />
        </span>
        <div>
          <p className="text-sm font-bold text-navy">{house?.name || 'Select a house'}</p>
          {house?.bird_capacity ? (
            <p className="text-xs text-navy/50">Capacity {house.bird_capacity} birds</p>
          ) : null}
        </div>
      </div>

      <div className="mt-2 flex gap-2">
        <div className="flex flex-1 gap-2">
          {ROUTINE_PERIODS.map((opt) => {
            const PeriodIcon = opt === 'morning' ? Sun : Moon
            return (
              <button
                key={opt}
                type="button"
                onClick={() => setPeriod(opt)}
                className={[
                  'flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-semibold capitalize transition-colors',
                  period === opt
                    ? 'border-forest bg-forest/10 text-forest'
                    : 'border-hairline text-navy/70 hover:bg-forest/5',
                ].join(' ')}
              >
                <PeriodIcon size={14} />
                {opt}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          onClick={() => setPeriod('emergency')}
          className={[
            'flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-bold uppercase tracking-wide transition-colors',
            period === 'emergency'
              ? 'border-critical bg-critical/10 text-critical'
              : 'border-critical/40 text-critical/70 hover:bg-critical/5',
          ].join(' ')}
        >
          <Siren size={14} />
          Emergency
        </button>
      </div>

      {houses.length > 1 ? (
        <select
          value={currentHouseId || ''}
          onChange={(e) => useAppStore.getState().selectHouse(e.target.value)}
          className="mt-2 w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
        >
          {houses.map((h) => (
            <option key={h.id} value={h.id}>
              {h.name}
            </option>
          ))}
        </select>
      ) : null}

      <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
        <SectionCard icon={Users} title="Birds">
          <NumberStepper
            label="Current bird count"
            value={birdCount}
            onChange={setBirdCount}
            placeholder={house?.bird_capacity ? String(house.bird_capacity) : '—'}
          />
          <NumberStepper label="Mortality today" value={mortality} onChange={setMortality} />
          <NumberStepper label="Sick / injured birds observed" value={sickOrInjured} onChange={setSickOrInjured} />
        </SectionCard>

        <SectionCard icon={Droplets} title="Consumption">
          <NumberStepper label="Feed consumed today (kg)" value={feedKg} onChange={setFeedKg} step={0.5} />
          <ToggleRow label="Water level" options={WATER_OPTIONS} value={waterLevel} onChange={setWaterLevel} />
          <NumberStepper label="Water consumed today (L) - optional" value={waterLiters} onChange={setWaterLiters} step={5} />
        </SectionCard>

        <SectionCard icon={Activity} title="Behaviour">
          <ToggleRow label="Activity" options={ACTIVITY_OPTIONS} value={activity} onChange={setActivity} />
          <ToggleRow label="Feeding behaviour" options={FEEDING_OPTIONS} value={feedingBehaviour} onChange={setFeedingBehaviour} />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setCrowding((v) => !v)}
              className={[
                'flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                crowding ? 'border-forest bg-forest/10 text-forest' : 'border-hairline text-navy/70',
              ].join(' ')}
            >
              Crowding observed
            </button>
            <button
              type="button"
              onClick={() => setUnusualSound((v) => !v)}
              className={[
                'flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                unusualSound ? 'border-forest bg-forest/10 text-forest' : 'border-hairline text-navy/70',
              ].join(' ')}
            >
              Unusual noise
            </button>
          </div>
        </SectionCard>

        <SectionCard icon={Thermometer} title="Environment (optional)" hint="Enter these only if reliable readings are available.">
          <div className="grid grid-cols-2 gap-3">
            <input
              type="number"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
              placeholder="Temperature (°C)"
              className="rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
            />
            <input
              type="number"
              value={humidity}
              onChange={(e) => setHumidity(e.target.value)}
              placeholder="Humidity (%)"
              className="rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
            />
          </div>
        </SectionCard>

        <SectionCard icon={Camera} title="Media">
          <div className="grid grid-cols-3 gap-2">
            <label className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-hairline py-3 text-xs font-medium text-navy hover:bg-forest/5">
              <Camera size={20} />
              Use Camera
              <input type="file" accept="image/*" capture="environment" onChange={handlePhotoChange} className="hidden" />
            </label>
            <label className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-hairline py-3 text-xs font-medium text-navy hover:bg-forest/5">
              <Upload size={20} />
              Upload Photo
              <input type="file" accept="image/*" onChange={handlePhotoChange} className="hidden" />
            </label>
            <button
              type="button"
              onClick={toggleRecording}
              className={[
                'flex flex-col items-center gap-1 rounded-lg border py-3 text-xs font-medium',
                isRecording ? 'border-critical bg-critical/10 text-critical' : 'border-hairline text-navy hover:bg-forest/5',
              ].join(' ')}
            >
              <Mic size={20} />
              {isRecording ? 'Stop Recording' : 'Record Sound'}
            </button>
          </div>
          {isUploadingPhoto ? <p className="text-xs text-navy/50">Uploading photo...</p> : null}
          {photo ? <p className="text-xs text-normal">Photo attached ✓</p> : null}
          {audio ? <p className="text-xs text-normal">Audio attached ✓</p> : null}
        </SectionCard>

        <SectionCard icon={StickyNote} title="Notes">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. Slightly reduced feeding near the east wall, otherwise normal..."
            rows={3}
            className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
          />
        </SectionCard>

        {error ? <p className="text-sm text-critical">{error}</p> : null}

        <button
          type="submit"
          disabled={isSubmitting || birdCount === ''}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-forest py-3 text-sm font-bold text-white hover:bg-forest-dark disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Sparkles size={16} />
              Analyze Flock
            </>
          )}
        </button>
        {!isSubmitting && birdCount === '' ? (
          <p className="text-center text-xs text-navy/40">Enter the current bird count above to analyze this check.</p>
        ) : null}
      </form>
    </div>
  )
}
