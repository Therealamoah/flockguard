import { useState } from 'react'
import { Sparkles, Send, Bot } from 'lucide-react'
import { api } from '../lib/api'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'
import { displayName, initialsFor } from '../lib/format'

const SUGGESTIONS = [
  'Which house should I inspect first?',
  'What changed since yesterday?',
  'Summarize my farm today.',
  'Has mortality increased this week?',
]

const AI_UNAVAILABLE_MESSAGE =
  "FlockGuard AI is temporarily unavailable right now. Your farm monitoring, Risk Engine, Radar and alerts are still working normally - please try asking again shortly."

export default function AskFlockGuardPage() {
  const { user } = useAuthStore()
  const { currentFarmId, houses } = useAppStore()
  const firstName = displayName(user).split(' ')[0]
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hi ${firstName} — I'm your farm intelligence assistant. Ask me anything about your houses, flocks or recent alerts.`,
    },
  ])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [houseId, setHouseId] = useState('')

  async function send(question) {
    const text = question ?? input
    if (!text.trim() || isSending) return

    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    setIsSending(true)
    try {
      const { answer } = await api.ask(text, { farmId: currentFarmId, houseId: houseId || undefined })
      setMessages((prev) => [...prev, { role: 'assistant', content: answer }])
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: AI_UNAVAILABLE_MESSAGE }])
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-65px)] max-w-4xl flex-col p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-ai/10 text-ai">
            <Sparkles size={20} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold text-navy">Ask FlockGuard</h1>
            <p className="text-sm text-navy/60">Your farm intelligence assistant.</p>
          </div>
        </div>
        {houses.length > 0 ? (
          <select
            value={houseId}
            onChange={(e) => setHouseId(e.target.value)}
            className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs font-medium text-navy outline-none focus:border-ai"
          >
            <option value="">Whole farm</option>
            {houses.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}
              </option>
            ))}
          </select>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => send(s)}
            className="rounded-full border border-hairline bg-surface px-3 py-1.5 text-xs font-medium text-navy/70 shadow-sm hover:border-ai/30 hover:bg-ai/10 hover:text-ai"
          >
            {s}
          </button>
        ))}
      </div>

      <div className="mt-4 flex-1 space-y-3 overflow-y-auto rounded-xl border border-hairline bg-surface p-4 shadow-sm">
        {messages.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex items-start gap-2'}>
            {m.role === 'assistant' ? (
              <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ai/10 text-ai">
                <Bot size={14} />
              </span>
            ) : null}
            <div
              className={[
                'max-w-lg rounded-2xl px-4 py-2.5 text-sm',
                m.role === 'user' ? 'rounded-tr-sm bg-forest text-white' : 'rounded-tl-sm bg-bg text-navy',
              ].join(' ')}
            >
              {m.content}
            </div>
            {m.role === 'user' ? (
              <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-forest/10 text-xs font-bold text-forest">
                {initialsFor(user)}
              </span>
            ) : null}
          </div>
        ))}
        {isSending ? (
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ai/10 text-ai">
              <Bot size={14} />
            </span>
            <span className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-bg px-4 py-2.5">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-navy/30 [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-navy/30 [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-navy/30" />
            </span>
          </div>
        ) : null}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
        className="mt-4 flex items-center gap-2 rounded-full border border-hairline bg-surface px-2 py-1.5 shadow-sm"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your farm..."
          className="flex-1 bg-transparent px-3 py-1.5 text-sm outline-none"
        />
        <button
          type="submit"
          disabled={isSending}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-forest text-white disabled:opacity-60"
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  )
}
