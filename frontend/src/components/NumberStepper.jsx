import { Minus, Plus } from 'lucide-react'

export default function NumberStepper({ label, value, onChange, min = 0, step = 1, placeholder = '—' }) {
  function adjust(delta) {
    const current = value === '' ? 0 : Number(value)
    const next = Math.max(min, current + delta)
    onChange(next)
  }

  return (
    <div>
      <label className="mb-1 block text-sm font-semibold text-navy">{label}</label>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => adjust(-step)}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-hairline text-navy hover:bg-forest/5"
        >
          <Minus size={16} />
        </button>
        <input
          type="number"
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          className="w-full rounded-lg border border-hairline px-3 py-2 text-center text-sm outline-none focus:border-forest"
        />
        <button
          type="button"
          onClick={() => adjust(step)}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-hairline text-navy hover:bg-forest/5"
        >
          <Plus size={16} />
        </button>
      </div>
    </div>
  )
}
