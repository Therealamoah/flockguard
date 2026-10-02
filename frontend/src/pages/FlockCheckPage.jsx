import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import NumberStepper from '../components/NumberStepper'
import StatusBadge from '../components/StatusBadge'
import { statusMeta } from '../lib/risk'
import { inspectionPriorities } from '../lib/riskFactors'
import { ACTIVITY_LABELS, FEEDING_LABELS, WATER_LABELS } from '../lib/checkLabels'
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
  RefreshCw,
  ScanLine,
  X,
} from 'lucide-react'
import PhotoAnalysisResult from '../components/PhotoAnalysisResult'
import ScanFlockCamera from '../components/ScanFlockCamera'

const BASELINE_SAMPLE_SIZE = 14 // mirrors backend/app/risk_engine/engine.py

// What the AI heard in a voice note and which form fields it filled in.
function VoiceNoteFeedback({ audio }) {
  if (!audio.transcript) {
    return (
      <p className="text-xs text-secondary">
        Voice note attached ✓ - but the AI couldn't make out any words. Try again somewhere quieter.
      </p>
    )
  }
  return (
    <div className="space-y-1 rounded-lg border border-hairline p-2 text-xs">
      <p className="flex items-center gap-1 font-semibold text-navy">
        <Mic size={14} /> AI heard your voice note
      </p>
      <p className="text-secondary">{audio.voice_fields?.heard || audio.transcript}</p>
      {audio.filled.length ? (
        <>
          <p className="pt-1 font-medium text-normal">Filled in for you - please check:</p>
          <div className="flex flex-wrap gap-1">
            {audio.filled.map((item) => (
              <span key={item} className="rounded-full bg-forest/10 px-2 py-0.5 text-forest">
                {item}
              </span>
            ))}
          </div>
        </>
      ) : (
        <p className="text-muted">Added to Notes below.</p>
      )}
    </div>
  )
}

// AI review of an uploaded Flock Check photo (backend grok_service.analyze_photo).
// photo_analysis is null when the vision model isn't available - fall back to
// a plain "attached" note so the photo still feels saved.
function PhotoFeedback({ photo, onRemove }) {
  const analysis = photo.photo_analysis
  const notPoultry = analysis && !analysis.is_poultry
  return (
    <div
      className={[
        'flex gap-3 rounded-lg border p-2',
        notPoultry ? 'border-warning/50 bg-warning/5' : 'border-hairline',
      ].join(' ')}
    >
      <img src={photo.url} alt="Uploaded flock" className="h-16 w-16 shrink-0 rounded object-cover" />
      <div className="min-w-0 flex-1">
        {analysis ? (
          <PhotoAnalysisResult analysis={analysis} />
        ) : (
          <p className="text-xs text-secondary">
            Photo attached ✓ - but the AI couldn't check it right now. Remove it and try again in a moment.
          </p>
        )}
      </div>
      <button type="button" onClick={onRemove} aria-label="Remove photo" className="self-start text-muted hover:text-critical">
        <X size={16} />
      </button>
    </div>
  )
}

function IconChip({ Icon }) {
  return (
    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-hairline/70 text-secondary">
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
      {hint ? <p className="mt-1 text-xs text-secondary">{hint}</p> : null}
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  )
}

const WATER_OPTIONS = Object.keys(WATER_LABELS)
const ACTIVITY_OPTIONS = Object.keys(ACTIVITY_LABELS)
const FEEDING_OPTIONS = Object.keys(FEEDING_LABELS)
const ROUTINE_PERIODS = ['morning', 'evening']

function ToggleRow({ label, options, labels, value, onChange }) {
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
              'flex-1 rounded-lg border px-2 py-2 text-sm font-medium transition-colors',
              value === opt
                ? 'border-forest bg-forest/10 text-forest'
                : 'border-hairline text-secondary hover:bg-forest/5',
            ].join(' ')}
          >
            {labels[opt]}
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
  if (sample.length < 2) return 'few checks'
  const newest = new Date(sample[0].recorded_at)
  const oldest = new Date(sample[sample.length - 1].recorded_at)
  const days = Math.max(1, Math.round((newest - oldest) / 86400000))
  return days === 1 ? 'day' : `${days} days`
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
  { mortality, sickOrInjured, feedKg, waterLiters, activity, feedingBehaviour, crowding, unusualSound, birdCount, previousBirdCount },
  priorChecks,
  houseName
) {
  const prior = priorChecks[0] || null
  const baseline = computeBaseline(priorChecks)
  const changes = []

  // Bird count - now auto-calculated (previous count minus today's mortality)
  // rather than farmer-entered, so it's worth surfacing as its own change.
  if (birdCount != null) {
    changes.push({
      Icon: Users,
      headline:
        previousBirdCount != null ? `Bird count now ${birdCount} (was ${previousBirdCount})` : `Bird count now ${birdCount}`,
      detail: 'Worked out from the dead birds you entered today.',
    })
  }

  // Mortality
  let headline
  if (prior) {
    if (mortality > prior.mortality) headline = `More dead birds: ${mortality} (was ${prior.mortality})`
    else if (mortality < prior.mortality) headline = `Fewer dead birds: ${mortality} (was ${prior.mortality})`
    else headline = `Same number of dead birds: ${mortality}`
  } else {
    headline = `Dead birds: ${mortality} (first check for this house)`
  }
  let detail = 'Not enough past checks yet to compare.'
  if (baseline.avgMortality != null) {
    const ratio = baseline.avgMortality > 0 ? mortality / baseline.avgMortality : mortality > 0 ? Infinity : 1
    const qualifier = ratio <= 1.1 ? 'About normal for' : ratio < 1.5 ? 'A little more than usual for' : ratio < 2.5 ? 'More than usual for' : 'Much more than usual for'
    detail = `${qualifier} ${houseName || 'this house'} over the last ${baseline.windowLabel}.`
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
          ? 'Eating the usual amount of feed'
          : diff < 0
            ? 'Eating less feed than usual'
            : 'Eating more feed than usual'
      feedDetail = `${feedKg}kg today - usually about ${Math.round(baseline.avgFeed)}kg.`
    } else {
      feedHeadline = 'Feed recorded'
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
        headline: `Drinking ${diff > 0 ? 'more' : 'less'} water: ${waterLiters}L (was ${prior.water_liters}L)`,
        detail: 'Compared with your last check.',
      })
    }
  }

  // Behaviour
  const behaviourFlags = []
  if (activity !== 'normal') behaviourFlags.push(ACTIVITY_LABELS[activity].toLowerCase())
  if (feedingBehaviour !== 'normal') behaviourFlags.push(FEEDING_LABELS[feedingBehaviour].toLowerCase())
  if (crowding) behaviourFlags.push('huddling together')
  if (unusualSound) behaviourFlags.push('coughing or strange sounds')
  if (sickOrInjured > 0) behaviourFlags.push(`${sickOrInjured} sick or hurt`)

  changes.push({
    Icon: ClipboardList,
    headline: behaviourFlags.length > 0 ? `Watch out: ${behaviourFlags.join(', ')}` : 'Birds look normal',
    detail: 'From what you saw during this check.',
  })

  return changes
}

export default function FlockCheckPage() {
  const { currentFarmId, currentHouseId, houses } = useAppStore()
  const navigate = useNavigate()
  const house = houses.find((h) => h.id === currentHouseId)

  const [period, setPeriod] = useState(() => (new Date().getHours() < 15 ? 'morning' : 'evening'))
  const [activeFlock, setActiveFlock] = useState(null)
  const [currentCount, setCurrentCount] = useState(null)
  const [isLoadingFlock, setIsLoadingFlock] = useState(true)
  const [showReconcile, setShowReconcile] = useState(false)
  const [reconcileValue, setReconcileValue] = useState('')
  const [reconcileReason, setReconcileReason] = useState('')
  const [isReconciling, setIsReconciling] = useState(false)
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
  const [isScanOpen, setIsScanOpen] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [isProcessingAudio, setIsProcessingAudio] = useState(false)
  const [audio, setAudio] = useState(null)
  const mediaRecorderRef = useRef(null)

  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [priorChecks, setPriorChecks] = useState([])
  const [explanation, setExplanation] = useState('')
  const [explanationLoading, setExplanationLoading] = useState(false)

  useEffect(() => {
    if (!currentFarmId || !currentHouseId) return
    let cancelled = false
    Promise.all([api.flocks.list(currentFarmId, currentHouseId), api.flockChecks.list(currentFarmId, currentHouseId)])
      .then(([flocks, checks]) => {
        if (cancelled) return
        const flock = flocks.find((f) => f.status === 'active') || null
        setActiveFlock(flock)
        setCurrentCount(flock ? (flock.current_bird_count ?? checks[0]?.bird_count ?? flock.initial_bird_count ?? 0) : null)
      })
      .finally(() => {
        if (!cancelled) setIsLoadingFlock(false)
      })
    return () => {
      cancelled = true
    }
  }, [currentFarmId, currentHouseId])

  function openReconcile() {
    setReconcileValue(currentCount != null ? String(currentCount) : '')
    setReconcileReason('')
    setShowReconcile(true)
  }

  async function handleReconcile() {
    if (!activeFlock) return
    const value = Number(reconcileValue)
    if (!Number.isFinite(value) || reconcileValue === '' || value < 0) {
      setError('Enter a valid bird count.')
      return
    }
    setIsReconciling(true)
    try {
      await api.flocks.reconcileCount(currentFarmId, currentHouseId, activeFlock.id, {
        current_bird_count: value,
        reason: reconcileReason || null,
      })
      setCurrentCount(value)
      setShowReconcile(false)
    } catch {
      setError('Could not update the bird count. Please try again.')
    } finally {
      setIsReconciling(false)
    }
  }

  async function handlePhotoChange(e) {
    const file = e.target.files?.[0]
    // Reset so picking the same file again (e.g. after removing it) still fires onChange.
    e.target.value = ''
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

  // Scan Flock already reviewed this frame - upload it without a second AI
  // call and keep the scan's analysis. Throws so the camera can show the error.
  async function attachScannedFrame(file, analysis) {
    const uploaded = await api.media.upload(file, 'image', { analyze: false })
    setPhoto({ ...uploaded, photo_analysis: analysis })
  }

  // Fills the form from what the farmer said (backend extract_check_fields
  // only returns fields they actually mentioned). Returns plain-language
  // labels of what changed so the farmer can review before submitting.
  function applyVoiceFields(fields) {
    if (!fields) return []
    const filled = []
    if (fields.mortality != null) {
      setMortality(fields.mortality)
      filled.push(`Dead birds: ${fields.mortality}`)
    }
    if (fields.sick_or_injured != null) {
      setSickOrInjured(fields.sick_or_injured)
      filled.push(`Sick or hurt: ${fields.sick_or_injured}`)
    }
    if (fields.feed_kg != null) {
      setFeedKg(String(fields.feed_kg))
      filled.push(`Feed: ${fields.feed_kg} kg`)
    }
    if (fields.water_level) {
      setWaterLevel(fields.water_level)
      filled.push(`Water: ${WATER_LABELS[fields.water_level].toLowerCase()}`)
    }
    if (fields.water_liters != null) {
      setWaterLiters(String(fields.water_liters))
      filled.push(`Water: ${fields.water_liters} L`)
    }
    if (fields.activity) {
      setActivity(fields.activity)
      filled.push(`Birds: ${ACTIVITY_LABELS[fields.activity].toLowerCase()}`)
    }
    if (fields.feeding_behaviour) {
      setFeedingBehaviour(fields.feeding_behaviour)
      filled.push(FEEDING_LABELS[fields.feeding_behaviour])
    }
    if (fields.crowding_observed != null) {
      setCrowding(fields.crowding_observed)
      filled.push(`Huddling: ${fields.crowding_observed ? 'yes' : 'no'}`)
    }
    if (fields.unusual_sound_observed != null) {
      setUnusualSound(fields.unusual_sound_observed)
      filled.push(`Coughing / strange sounds: ${fields.unusual_sound_observed ? 'yes' : 'no'}`)
    }
    if (fields.temperature_c != null) {
      setTemperature(String(fields.temperature_c))
      filled.push(`Temperature: ${fields.temperature_c}°C`)
    }
    if (fields.humidity_pct != null) {
      setHumidity(String(fields.humidity_pct))
      filled.push(`Humidity: ${fields.humidity_pct}%`)
    }
    return filled
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
        setIsProcessingAudio(true)
        try {
          const uploaded = await api.media.upload(file, 'video')
          if (uploaded.transcript) {
            setNotes((prev) => (prev.trim() ? `${prev.trim()}\n\n🎤 ${uploaded.transcript}` : uploaded.transcript))
          }
          setAudio({ ...uploaded, filled: applyVoiceFields(uploaded.voice_fields) })
        } catch {
          setError('Audio upload failed. You can still submit without it.')
        } finally {
          setIsProcessingAudio(false)
        }
      }
      mediaRecorderRef.current = recorder
      recorder.start()
      setIsRecording(true)
    } catch {
      setError('Could not access the microphone.')
    }
  }

  async function generateExplanation(response) {
    setExplanationLoading(true)
    try {
      // Grounded in the check's own persisted risk data (previous score,
      // risk_change, morning/evening comparison, open alert) rather than a
      // hand-built prompt - see app/api/routes/ask.py::explain_check.
      const { available, explanation: text } = await api.askExplain(currentFarmId, currentHouseId, response.id)
      setExplanation(
        available
          ? text
          : "The AI can't explain this right now. Your checks and risk numbers still work as normal."
      )
    } catch {
      setExplanation(
        "The AI can't explain this right now. Your checks and risk numbers still work as normal."
      )
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
    if (!activeFlock) {
      setError('Place an active flock in this house before logging a Flock Check.')
      return
    }
    // Basic client-side validation to avoid sending invalid payloads
    const mortalityNum = Number(mortality)

    if (!Number.isFinite(mortalityNum) || mortalityNum < 0) {
      setError('Enter the number of dead birds (0 or more).')
      return
    }
    if (currentCount != null && mortalityNum > currentCount) {
      setError('Dead birds cannot be more than the birds in the house.')
      return
    }

    setIsSubmitting(true)
    try {
      const fetchedPriorChecks = await api.flockChecks.list(currentFarmId, currentHouseId)

      const response = await api.flockChecks.submit(currentFarmId, currentHouseId, {
        period,
        mortality: mortalityNum,
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
      setCurrentCount(response.bird_count)
      setPriorChecks(fetchedPriorChecks)

      if (response.risk_status !== 'normal') {
        generateExplanation(response)
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
      {
        mortality,
        sickOrInjured,
        feedKg,
        waterLiters,
        activity,
        feedingBehaviour,
        crowding,
        unusualSound,
        birdCount: result.bird_count,
        previousBirdCount: priorChecks[0]?.bird_count ?? null,
      },
      priorChecks,
      house?.name
    )
    const priorities = inspectionPriorities(result.risk_factors)

    return (
      <div className="mx-auto max-w-2xl p-6">
        <div className="overflow-hidden rounded-xl border border-hairline bg-surface shadow-sm">
          <div className="p-6 text-center" style={{ backgroundColor: `${meta.color}14` }}>
            <p className="text-xs font-bold uppercase tracking-wide text-secondary">Check saved</p>
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
            {result.previous_risk_score != null ? (
              <p className="mt-2 text-sm font-semibold text-secondary">
                {result.previous_risk_score} → {result.risk_score}
                <span style={{ color: meta.color }}>
                  {' '}
                  ({result.risk_change > 0 ? '+' : ''}
                  {result.risk_change})
                </span>
              </p>
            ) : null}
          </div>
        </div>

        {result.morning_comparison ? (
          <div className="mt-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest/10 text-forest">
                <Sun size={14} />
              </span>
              <h2 className="text-sm font-bold text-navy">Morning vs {result.period === 'emergency' ? 'this check' : 'Evening'}</h2>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-xs text-muted">Morning</p>
                <p className="font-display text-lg font-extrabold text-navy">{result.morning_comparison.morning_risk_score}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Now</p>
                <p className="font-display text-lg font-extrabold text-navy">{result.morning_comparison.evening_risk_score}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Change</p>
                <p className="font-display text-lg font-extrabold" style={{ color: meta.color }}>
                  {result.morning_comparison.risk_change > 0 ? '+' : ''}
                  {result.morning_comparison.risk_change}
                </p>
              </div>
            </div>
            <ul className="mt-4 space-y-1.5 text-sm text-secondary">
              <li>Dead birds change: {result.morning_comparison.mortality_change > 0 ? '+' : ''}{result.morning_comparison.mortality_change}</li>
              {result.morning_comparison.feed_change != null ? (
                <li>
                  Feed change: {result.morning_comparison.feed_change > 0 ? '+' : ''}
                  {result.morning_comparison.feed_change}kg
                </li>
              ) : null}
              {result.morning_comparison.water_changed ? <li>Water drinking changed since morning</li> : null}
              {result.morning_comparison.activity_changed ? <li>How active the birds are changed since morning</li> : null}
            </ul>
          </div>
        ) : null}

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
                  <p className="text-xs text-secondary">{c.detail}</p>
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
              <h2 className="text-sm font-bold text-navy">Why FlockGuard is worried</h2>
            </div>
            <p className="mt-3 flex items-center gap-2 text-sm text-secondary">
              {explanationLoading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Explaining...
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
              <h2 className="text-sm font-bold text-navy">What to check first</h2>
            </div>
            <ol className="mt-4 space-y-3">
              {priorities.map((p, i) => (
                <li key={p.key} className="flex gap-3">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-hairline/70 text-xs font-bold text-navy">
                    {i + 1}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-navy">{p.headline}</p>
                    <p className="text-xs text-secondary">{p.detail}</p>
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
            See house
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
            Record what you found
          </button>
        </div>
      </div>
    )
  }

  if (currentHouseId && isLoadingFlock) {
    return (
      <div className="flex items-center justify-center gap-2 p-6 text-sm text-secondary">
        <Loader2 size={16} className="animate-spin" />
        Loading house data...
      </div>
    )
  }

  if (currentHouseId && !activeFlock) {
    return (
      <div className="mx-auto max-w-xl p-6">
        <div className="rounded-xl border border-hairline bg-surface p-6 text-center shadow-sm">
          <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-forest/10 text-forest">
            <Warehouse size={20} />
          </span>
          <p className="mt-3 text-sm font-bold text-navy">No active flock in this house</p>
          <p className="mt-1 text-sm text-secondary">Place a flock before logging a Flock Check.</p>
        </div>
      </div>
    )
  }

  const mortalityPreviewNum = Number(mortality) || 0
  const projectedCount = currentCount != null ? Math.max(0, currentCount - mortalityPreviewNum) : null

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
            <p className="text-xs text-secondary">Capacity {house.bird_capacity} birds</p>
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
                    : 'border-hairline text-secondary hover:bg-forest/5',
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
          <div>
            <label className="mb-1 block text-sm font-semibold text-navy">Birds in this house now</label>
            <div className="rounded-lg border border-hairline bg-hairline/20 px-3 py-2 text-center text-sm font-bold text-navy">
              {currentCount ?? '—'}
            </div>
            {mortalityPreviewNum > 0 && projectedCount != null ? (
              <p className="mt-1 text-xs text-secondary">→ {projectedCount} after today's dead birds</p>
            ) : null}
            <button
              type="button"
              onClick={() => (showReconcile ? setShowReconcile(false) : openReconcile())}
              className="mt-1.5 flex items-center gap-1 text-xs font-semibold text-forest hover:underline"
            >
              <RefreshCw size={12} />
              You counted a different number? Fix it here
            </button>
            {showReconcile ? (
              <div className="mt-2 space-y-2 rounded-lg border border-hairline p-3">
                <input
                  type="number"
                  min="0"
                  value={reconcileValue}
                  onChange={(e) => setReconcileValue(e.target.value)}
                  placeholder="How many birds you counted"
                  className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
                />
                <input
                  type="text"
                  value={reconcileReason}
                  onChange={(e) => setReconcileReason(e.target.value)}
                  placeholder="Why is it different? (optional)"
                  className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={isReconciling}
                    onClick={handleReconcile}
                    className="flex-1 rounded-lg bg-forest px-3 py-2 text-xs font-bold text-white hover:bg-forest-dark disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isReconciling ? 'Saving...' : 'Save count'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowReconcile(false)}
                    className="rounded-lg border border-hairline px-3 py-2 text-xs font-bold text-navy hover:bg-forest/5"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : null}
          </div>
          <NumberStepper label="Dead birds today" value={mortality} onChange={setMortality} />
          <NumberStepper label="Sick or hurt birds" value={sickOrInjured} onChange={setSickOrInjured} />
        </SectionCard>

        <SectionCard icon={Droplets} title="Feed & Water">
          <NumberStepper label="Feed eaten today (kg)" value={feedKg} onChange={setFeedKg} step={0.5} />
          <ToggleRow
            label="How much water did they drink?"
            options={WATER_OPTIONS}
            labels={WATER_LABELS}
            value={waterLevel}
            onChange={setWaterLevel}
          />
          <NumberStepper label="Water drunk today (litres) - if you measured it" value={waterLiters} onChange={setWaterLiters} step={5} />
        </SectionCard>

        <SectionCard icon={Activity} title="How the birds look">
          <ToggleRow
            label="Are the birds moving around?"
            options={ACTIVITY_OPTIONS}
            labels={ACTIVITY_LABELS}
            value={activity}
            onChange={setActivity}
          />
          <ToggleRow
            label="Are they eating?"
            options={FEEDING_OPTIONS}
            labels={FEEDING_LABELS}
            value={feedingBehaviour}
            onChange={setFeedingBehaviour}
          />
          <p className="text-sm font-semibold text-navy">Did you see or hear any of these?</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setCrowding((v) => !v)}
              className={[
                'flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                crowding ? 'border-forest bg-forest/10 text-forest' : 'border-hairline text-secondary',
              ].join(' ')}
            >
              Huddling together
            </button>
            <button
              type="button"
              onClick={() => setUnusualSound((v) => !v)}
              className={[
                'flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                unusualSound ? 'border-forest bg-forest/10 text-forest' : 'border-hairline text-secondary',
              ].join(' ')}
            >
              Coughing / strange sounds
            </button>
          </div>
        </SectionCard>

        <SectionCard
          icon={Thermometer}
          title="House temperature (optional)"
          hint="Only fill this in if you have a thermometer in the house."
        >
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

        <SectionCard icon={Camera} title="Photos & Voice">
          {isScanOpen ? <ScanFlockCamera onClose={() => setIsScanOpen(false)} onAttach={attachScannedFrame} /> : null}
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => setIsScanOpen(true)}
              className="flex flex-col items-center gap-1 rounded-lg border border-forest bg-forest py-3 text-xs font-semibold text-white hover:opacity-90"
            >
              <ScanLine size={20} />
              AI Camera
            </button>
            <label className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-hairline py-3 text-xs font-medium text-navy hover:bg-forest/5">
              <Upload size={20} />
              Upload Photo
              <input type="file" accept="image/*" onChange={handlePhotoChange} className="hidden" />
            </label>
            <button
              type="button"
              onClick={toggleRecording}
              disabled={isProcessingAudio}
              className={[
                'flex flex-col items-center gap-1 rounded-lg border py-3 text-xs font-medium disabled:opacity-60',
                isRecording ? 'border-critical bg-critical/10 text-critical' : 'border-hairline text-navy hover:bg-forest/5',
              ].join(' ')}
            >
              <Mic size={20} />
              {isRecording ? 'Stop Recording' : 'Record Voice Note'}
            </button>
          </div>
          <p className="text-[11px] text-muted">
            Point the AI Camera at your birds or upload a photo for instant feedback. Or just say your check out loud -
            the AI fills in the form for you.
          </p>
          {isUploadingPhoto ? (
            <p className="flex items-center gap-1 text-xs text-secondary">
              <Loader2 size={12} className="animate-spin" /> AI is checking your photo...
            </p>
          ) : null}
          {photo ? <PhotoFeedback photo={photo} onRemove={() => setPhoto(null)} /> : null}
          {isProcessingAudio ? (
            <p className="flex items-center gap-1 text-xs text-secondary">
              <Loader2 size={12} className="animate-spin" /> AI is listening to your voice note...
            </p>
          ) : null}
          {audio ? <VoiceNoteFeedback audio={audio} /> : null}
        </SectionCard>

        <SectionCard icon={StickyNote} title="Notes">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. Birds near the east wall are eating less, the rest look fine..."
            rows={3}
            className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
          />
        </SectionCard>

        {error ? <p className="text-sm text-critical">{error}</p> : null}

        <button
          type="submit"
          disabled={isSubmitting || currentCount == null}
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
      </form>
    </div>
  )
}
