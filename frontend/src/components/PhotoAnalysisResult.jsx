import { ImageOff, Sparkles } from 'lucide-react'

// Renders a backend PhotoAnalysis (grok_service.analyze_photo) - shared by
// the Flock Check photo card and the Scan Flock AI camera.
export default function PhotoAnalysisResult({ analysis }) {
  if (!analysis.is_poultry) {
    return (
      <div className="space-y-1 text-xs">
        <p className="flex items-center gap-1 font-semibold text-warning">
          <ImageOff size={14} /> This doesn't look like poultry
        </p>
        <p className="text-secondary">{analysis.summary}</p>
      </div>
    )
  }
  return (
    <div className="space-y-1 text-xs">
      <p className="flex items-center gap-1 font-semibold text-navy">
        <Sparkles size={14} /> AI photo check
      </p>
      <p className="text-secondary">{analysis.summary}</p>
      {analysis.observations.length ? (
        <ul className="list-disc pl-4 text-secondary">
          {analysis.observations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {analysis.concerns.length ? (
        <ul className="list-disc pl-4 text-warning">
          {analysis.concerns.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      <p className="text-[10px] text-muted">Based only on what's visible - not a diagnosis.</p>
    </div>
  )
}
