import { useEffect, useRef, useState } from 'react'
import {
  Sparkles,
  Send,
  Bot,
  RotateCcw,
  Building2,
  Clock,
  ClipboardList,
  ClipboardCheck,
  TrendingUp,
  ShieldAlert,
  BarChart3,
  Bell,
} from 'lucide-react'
import { api } from '../lib/api'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'
import { displayName, initialsFor } from '../lib/format'

const SUGGESTIONS = [
  { Icon: ShieldAlert, text: 'Which house should I inspect first?' },
  { Icon: Clock, text: 'What changed since yesterday?' },
  { Icon: ClipboardList, text: 'Summarize my farm today.' },
  { Icon: TrendingUp, text: 'Has mortality increased this week?' },
  { Icon: Building2, text: 'Which house has the highest risk score?' },
  { Icon: ClipboardCheck, text: "What should I check during today's inspection?" },
  { Icon: BarChart3, text: 'Compare this week to last week.' },
  { Icon: Bell, text: 'Any unresolved alerts I should know about?' },
]

const QUICK_CHIPS = SUGGESTIONS.slice(0, 4)

const AI_UNAVAILABLE_MESSAGE =
  "FlockGuard AI is temporarily unavailable right now. Your farm monitoring, Risk Engine, Radar and alerts are still working normally - please try asking again shortly."

const SESSION_EXPIRED_MESSAGE = "Your session couldn't be verified - please refresh the page and try again."

const OFFLINE_MESSAGE = "Couldn't reach FlockGuard - check your internet connection and try again."

function messageForAskError(err) {
  // A network-level failure (offline, DNS hiccup, no route to the server)
  // never gets a response at all, so apiFetch never sets err.status - that
  // distinguishes it from a real HTTP error the backend actually returned.
  if (!err?.status) return OFFLINE_MESSAGE
  // 401 here almost always means Firebase couldn't refresh the ID token
  // (itself usually caused by the same kind of connectivity hiccup) - the
  // AI is not the problem, the request never got a valid Authorization
  // header, so say so rather than blaming "AI unavailable."
  if (err.status === 401) return SESSION_EXPIRED_MESSAGE
  return AI_UNAVAILABLE_MESSAGE
}

function timeGreeting() {
  const hour = new Date().getHours()
  if (hour < 5) return 'Good night'
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function formatTime(date) {
  return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

export default function AskFlockGuardPage() {
  const { user } = useAuthStore()
  const { currentFarmId, houses } = useAppStore()
  const firstName = displayName(user).split(' ')[0]
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [houseId, setHouseId] = useState('')
  const textareaRef = useRef(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (messages.length === 0) return
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isSending])

  function resizeTextarea() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 128)}px`
  }

  async function send(question) {
    const text = (question ?? input).trim()
    if (!text || isSending) return

    setMessages((prev) => [...prev, { role: 'user', content: text, at: new Date() }])
    setInput('')
    requestAnimationFrame(resizeTextarea)
    setIsSending(true)
    try {
      const { answer } = await api.ask(text, { farmId: currentFarmId, houseId: houseId || undefined })
      setMessages((prev) => [...prev, { role: 'assistant', content: answer, at: new Date() }])
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: messageForAskError(err), at: new Date() }])
    } finally {
      setIsSending(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="mx-auto flex h-[calc(100vh-65px)] max-w-4xl flex-col p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-ai/20 to-ai/5 text-ai ring-1 ring-ai/15">
            <Sparkles size={20} />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-display text-2xl font-extrabold text-navy">Ask FlockGuard</h1>
              <span className="hidden rounded-full bg-ai/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ai sm:inline-block">
                AI
              </span>
            </div>
            <p className="text-sm text-secondary">Grounded in your farm's real data.</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {houses.length > 0 ? (
            <div className="relative">
              <Building2 size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
              <select
                value={houseId}
                onChange={(e) => setHouseId(e.target.value)}
                className="rounded-lg border border-hairline bg-surface py-2 pl-7 pr-3 text-xs font-medium text-navy outline-none focus:border-ai"
              >
                <option value="">Whole farm</option>
                {houses.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.name}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {!isEmpty ? (
            <button
              onClick={() => setMessages([])}
              className="flex items-center gap-1.5 rounded-lg border border-hairline bg-surface px-3 py-2 text-xs font-medium text-secondary hover:border-ai/30 hover:text-ai"
              title="Start a new conversation"
            >
              <RotateCcw size={13} />
              New chat
            </button>
          ) : null}
        </div>
      </div>

      {!isEmpty ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {QUICK_CHIPS.map(({ Icon, text }) => (
            <button
              key={text}
              onClick={() => send(text)}
              disabled={isSending}
              className="flex items-center gap-1.5 rounded-full border border-hairline bg-surface px-3 py-1.5 text-xs font-medium text-secondary shadow-sm hover:border-ai/30 hover:bg-ai/10 hover:text-ai disabled:opacity-50"
            >
              <Icon size={12} className="shrink-0" />
              {text}
            </button>
          ))}
        </div>
      ) : null}

      <div
        ref={scrollRef}
        className="mt-4 flex-1 overflow-y-auto rounded-2xl border border-hairline bg-surface shadow-sm"
      >
        {isEmpty ? (
          <div className="flex min-h-full flex-col items-center justify-center px-6 py-10 text-center">
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-linear-to-br from-ai/20 to-ai/5 text-ai ring-1 ring-ai/15">
              <Bot size={30} />
            </span>
            <h2 className="mt-5 font-display text-xl font-extrabold text-navy sm:text-2xl">
              {timeGreeting()}, {firstName}.
            </h2>
            <p className="mt-2 max-w-md text-sm text-secondary">
              I'm your farm intelligence assistant. Ask me anything about your houses, flocks, risk scores, or
              recent alerts - every answer is grounded in your farm's actual data.
            </p>

            <div className="mt-8 grid w-full max-w-2xl grid-cols-1 gap-2.5 sm:grid-cols-2">
              {SUGGESTIONS.map(({ Icon, text }) => (
                <button
                  key={text}
                  onClick={() => send(text)}
                  className="flex items-center gap-3 rounded-xl border border-hairline bg-bg px-4 py-3 text-left text-sm font-medium text-navy transition-colors hover:border-ai/30 hover:bg-ai/10 hover:text-ai"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ai/10 text-ai">
                    <Icon size={15} />
                  </span>
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4 p-4">
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex items-start gap-2.5'}>
                {m.role === 'assistant' ? (
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-ai/20 to-ai/5 text-ai ring-1 ring-ai/15">
                    <Bot size={15} />
                  </span>
                ) : null}
                <div className={m.role === 'user' ? 'flex max-w-lg flex-col items-end' : 'flex max-w-lg flex-col items-start'}>
                  <div
                    className={[
                      'rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words',
                      m.role === 'user' ? 'rounded-tr-sm bg-forest text-white' : 'rounded-tl-sm bg-bg text-navy',
                    ].join(' ')}
                  >
                    {m.content}
                  </div>
                  <span className="mt-1 px-1 text-[11px] text-muted">{formatTime(m.at)}</span>
                </div>
                {m.role === 'user' ? (
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-forest/10 text-xs font-bold text-forest">
                    {initialsFor(user)}
                  </span>
                ) : null}
              </div>
            ))}
            {isSending ? (
              <div className="flex items-start gap-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-ai/20 to-ai/5 text-ai ring-1 ring-ai/15">
                  <Bot size={15} />
                </span>
                <span className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-bg px-4 py-3">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-navy/30 [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-navy/30 [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-navy/30" />
                </span>
              </div>
            ) : null}
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
        className="mt-4 flex items-end gap-2 rounded-2xl border border-hairline bg-surface p-2 shadow-sm focus-within:border-ai/40"
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => {
            setInput(e.target.value)
            resizeTextarea()
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your farm..."
          className="max-h-32 flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none"
        />
        <button
          type="submit"
          disabled={isSending || !input.trim()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-forest text-white transition-opacity disabled:opacity-40"
        >
          <Send size={16} />
        </button>
      </form>
      <p className="mt-2 text-center text-[11px] text-muted">
        FlockGuard AI can make mistakes. Always verify critical farm decisions.
      </p>
    </div>
  )
}
