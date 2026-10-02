import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, ScanLine, Paperclip, X } from 'lucide-react'
import { api } from '../lib/api'
import PhotoAnalysisResult from './PhotoAnalysisResult'

// Long side of the frame sent to the AI - plenty for a vision model and
// keeps each scan a few hundred KB on a farm mobile connection.
const SCAN_MAX_SIDE = 1024

// Auto-scan runs a tiny on-device motion check (no network, no AI) and
// only calls the AI once the farmer holds steady on a view that differs
// from the last one scanned - so pointing the phone "just works" without
// streaming every frame to Groq. Diffs are mean absolute luminance (0-255)
// over a 32x24 grayscale thumbnail.
const SAMPLE_W = 32
const SAMPLE_H = 24
const SAMPLE_MS = 400
const MOTION_THRESHOLD = 10 // above this between samples = phone is moving
const STEADY_MS = 1200 // hold this long before auto-scanning
const NEW_SCENE_THRESHOLD = 18 // above this vs the last scan = a new view worth scanning
const MIN_GAP_MS = 4000 // between auto-scans (backend allows 20/minute)
const BACKOFF_MS = 15000 // after a failed/unavailable scan
const DARK_LUMA = 30

function captureFrame(video) {
  const scale = Math.min(1, SCAN_MAX_SIDE / Math.max(video.videoWidth, video.videoHeight))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(video.videoWidth * scale)
  canvas.height = Math.round(video.videoHeight * scale)
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.82))
}

function sampleLuma(video, canvas) {
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  ctx.drawImage(video, 0, 0, SAMPLE_W, SAMPLE_H)
  const { data } = ctx.getImageData(0, 0, SAMPLE_W, SAMPLE_H)
  const luma = new Uint8Array(SAMPLE_W * SAMPLE_H)
  for (let i = 0; i < luma.length; i++) {
    luma[i] = (data[i * 4] * 299 + data[i * 4 + 1] * 587 + data[i * 4 + 2] * 114) / 1000
  }
  return luma
}

function meanDiff(a, b) {
  let total = 0
  for (let i = 0; i < a.length; i++) total += Math.abs(a[i] - b[i])
  return total / a.length
}

function meanLuma(a) {
  let total = 0
  for (let i = 0; i < a.length; i++) total += a[i]
  return total / a.length
}

// Full-screen "Scan Flock" AI camera: live viewfinder that auto-scans when
// the farmer holds steady on something new (or on tap), with feedback
// updating live. Scans aren't stored (POST /media/scan); only a frame the
// farmer attaches is uploaded, via onAttach.
export default function ScanFlockCamera({ onClose, onAttach }) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const sampleCanvasRef = useRef(null)
  const prevSampleRef = useRef(null)
  const lastScannedSampleRef = useRef(null)
  const steadySinceRef = useRef(0)
  const nextAllowedAtRef = useRef(0)
  const isScanningRef = useRef(false)

  const [cameraError, setCameraError] = useState(() =>
    navigator.mediaDevices?.getUserMedia ? '' : 'This browser cannot open the camera. Use "Upload Photo" instead.'
  )
  const [isReady, setIsReady] = useState(false)
  const [autoScan, setAutoScan] = useState(true)
  const [hint, setHint] = useState('')
  const [isScanning, setIsScanning] = useState(false)
  const [lastScan, setLastScan] = useState(null) // { file, previewUrl, result: FlockScanResponse }
  const [scanError, setScanError] = useState('')
  const [isAttaching, setIsAttaching] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (!navigator.mediaDevices?.getUserMedia) return
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        videoRef.current.srcObject = stream
      })
      .catch(() => setCameraError('Could not open the camera. Allow camera access, or use "Upload Photo" instead.'))
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  useEffect(() => {
    return () => {
      if (lastScan) URL.revokeObjectURL(lastScan.previewUrl)
    }
  }, [lastScan])

  const runScan = useCallback(async () => {
    const video = videoRef.current
    if (!video?.videoWidth || isScanningRef.current) return
    isScanningRef.current = true
    setIsScanning(true)
    setScanError('')
    if (sampleCanvasRef.current) lastScannedSampleRef.current = sampleLuma(video, sampleCanvasRef.current)
    let ok = false
    try {
      const blob = await captureFrame(video)
      if (!blob) return
      const file = new File([blob], 'flock-scan.jpg', { type: 'image/jpeg' })
      const result = await api.media.scan(file)
      ok = result.available
      setLastScan({ file, previewUrl: URL.createObjectURL(blob), result })
    } catch (err) {
      setScanError(
        err?.name === 'TimeoutError'
          ? 'The scan took too long - your connection may be slow.'
          : 'Scan failed. Check your connection.'
      )
    } finally {
      // A failed scan shouldn't mark this view as "done" - retry it after the backoff.
      if (!ok) lastScannedSampleRef.current = null
      nextAllowedAtRef.current = Date.now() + (ok ? MIN_GAP_MS : BACKOFF_MS)
      isScanningRef.current = false
      setIsScanning(false)
    }
  }, [])

  useEffect(() => {
    if (!autoScan || !isReady || cameraError) return
    steadySinceRef.current = Date.now()
    prevSampleRef.current = null
    const id = setInterval(() => {
      const video = videoRef.current
      if (!video?.videoWidth || !sampleCanvasRef.current || document.hidden) return
      const sample = sampleLuma(video, sampleCanvasRef.current)
      const prev = prevSampleRef.current
      prevSampleRef.current = sample
      if (!prev) return

      const now = Date.now()
      if (meanDiff(sample, prev) > MOTION_THRESHOLD) {
        steadySinceRef.current = now
        setHint('Hold the phone steady...')
        return
      }
      if (meanLuma(sample) < DARK_LUMA) {
        setHint('Too dark - move closer to the light')
        return
      }
      setHint('')
      if (now - steadySinceRef.current < STEADY_MS || isScanningRef.current || now < nextAllowedAtRef.current) return
      const last = lastScannedSampleRef.current
      if (last && meanDiff(sample, last) < NEW_SCENE_THRESHOLD) return // same view as last scan
      runScan()
    }, SAMPLE_MS)
    return () => clearInterval(id)
  }, [autoScan, isReady, cameraError, runScan])

  async function handleAttach() {
    setIsAttaching(true)
    try {
      await onAttach(lastScan.file, lastScan.result.analysis)
      onClose()
    } catch {
      setScanError('Could not attach the photo. Try again.')
      setIsAttaching(false)
    }
  }

  const analysis = lastScan?.result.available ? lastScan.result.analysis : null
  const topHint = hint || (lastScan || isScanning ? '' : autoScan ? 'Point the camera at your birds' : 'Tap the button to scan')

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black text-white">
      <canvas ref={sampleCanvasRef} width={SAMPLE_W} height={SAMPLE_H} className="hidden" />
      <div className="flex items-center justify-between px-4 py-3">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <ScanLine size={18} /> Scan Flock
        </p>
        <button type="button" onClick={onClose} aria-label="Close camera" className="rounded-full p-1 hover:bg-white/10">
          <X size={22} />
        </button>
      </div>

      <div className="relative flex-1 overflow-hidden">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          onLoadedData={() => setIsReady(true)}
          className="absolute inset-0 h-full w-full object-cover"
        />

        {/* Viewfinder corners */}
        <div className="pointer-events-none absolute inset-8 sm:inset-16">
          <span className="absolute left-0 top-0 h-8 w-8 rounded-tl-lg border-l-4 border-t-4 border-white/80" />
          <span className="absolute right-0 top-0 h-8 w-8 rounded-tr-lg border-r-4 border-t-4 border-white/80" />
          <span className="absolute bottom-0 left-0 h-8 w-8 rounded-bl-lg border-b-4 border-l-4 border-white/80" />
          <span className="absolute bottom-0 right-0 h-8 w-8 rounded-br-lg border-b-4 border-r-4 border-white/80" />
          {isScanning ? (
            <span className="absolute left-0 right-0 h-0.5 animate-[scan-line_2s_ease-in-out_infinite] bg-forest shadow-[0_0_12px_2px] shadow-forest" />
          ) : null}
        </div>

        {cameraError ? (
          <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm">{cameraError}</div>
        ) : !isReady ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="animate-spin" size={28} />
          </div>
        ) : topHint ? (
          <p className="absolute inset-x-0 top-4 text-center text-xs text-white/90 [text-shadow:0_1px_3px_rgb(0_0_0/0.8)]">
            {topHint}
          </p>
        ) : null}
      </div>

      <div className="space-y-3 px-4 pb-6 pt-3">
        {isScanning ? <p className="text-center text-sm">Checking your birds...</p> : null}
        {scanError ? <p className="text-center text-sm text-critical">{scanError}</p> : null}
        {lastScan && !lastScan.result.available && !isScanning ? (
          <p className="text-center text-sm">AI photo check is unavailable right now. Try again in a moment.</p>
        ) : null}
        {analysis ? (
          <div className="flex max-h-[40vh] gap-3 overflow-y-auto rounded-xl bg-surface p-3 text-navy">
            <img src={lastScan.previewUrl} alt="Last scanned view" className="h-14 w-14 shrink-0 rounded object-cover" />
            <div className="min-w-0 flex-1">
              <PhotoAnalysisResult analysis={analysis} />
            </div>
          </div>
        ) : null}

        <div className="grid grid-cols-3 items-center">
          <button
            type="button"
            onClick={() => setAutoScan((on) => !on)}
            aria-pressed={autoScan}
            className={[
              'justify-self-start rounded-full border px-3 py-1.5 text-xs font-medium',
              autoScan ? 'border-forest bg-forest/20 text-white' : 'border-white/40 text-white/70',
            ].join(' ')}
          >
            Auto-scan {autoScan ? 'on' : 'off'}
          </button>
          <button
            type="button"
            onClick={runScan}
            disabled={!isReady || !!cameraError || isScanning}
            aria-label="Scan now"
            className="flex h-16 w-16 items-center justify-center justify-self-center rounded-full border-4 border-white bg-forest disabled:opacity-40"
          >
            {isScanning ? <Loader2 className="animate-spin" size={26} /> : <ScanLine size={26} />}
          </button>
          {analysis?.is_poultry ? (
            <button
              type="button"
              onClick={handleAttach}
              disabled={isAttaching || isScanning}
              className="flex items-center gap-1 justify-self-end rounded-full bg-forest px-3 py-1.5 text-xs font-semibold disabled:opacity-60"
            >
              {isAttaching ? <Loader2 className="animate-spin" size={14} /> : <Paperclip size={14} />}
              Attach
            </button>
          ) : (
            <span />
          )}
        </div>
      </div>
    </div>
  )
}
