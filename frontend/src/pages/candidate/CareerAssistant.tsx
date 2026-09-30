// "Ask the career assistant": a simple chat whose answers come from candidateApi.ask(), a set of
// rules over the career paths shown on the page. No AI model is called.
import { MessageCircleQuestion, RotateCcw, Send } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { Pill } from '@/components/badges'
import { Panel } from '@/components/headers'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { candidateApi } from '@/lib/api/candidateApi'
import type { CareerPath } from '@/lib/api/types'
import { cn } from '@/lib/utils'

const SUGGESTIONS = [
  'Which EV jobs are growing?',
  'Which course should I take?',
  'What about solar?',
  'Which jobs are declining?',
  'Tell me about EV Service Technician',
]

type Message = { id: number; from: 'you' | 'assistant'; text: string }

function Bubble({ from, children }: { from: Message['from']; children: string }) {
  const mine = from === 'you'
  return (
    <li className={cn('flex flex-col gap-1', mine ? 'items-end' : 'items-start')}>
      <span className="text-[11px] font-medium text-muted-foreground">
        {mine ? 'You' : 'Assistant'}
        <span className="sr-only">:</span>
      </span>
      <p
        className={cn(
          'max-w-[90%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed',
          mine
            ? 'rounded-br-sm bg-primary text-primary-foreground'
            : 'rounded-bl-sm border bg-muted/60 text-foreground',
        )}
      >
        {children}
      </p>
    </li>
  )
}

export function CareerAssistant({
  paths,
  districtLabel,
  ready,
  loading,
}: {
  /** All career paths of the district, ranked by demand (the numbers on this page). */
  paths: CareerPath[]
  districtLabel: string
  ready: boolean
  loading: boolean
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const nextId = useRef(0)
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [messages])

  function send(question: string) {
    const text = question.trim()
    if (!text || !ready) return
    const answer = candidateApi.ask(text, paths)
    setMessages((current) => [
      ...current,
      { id: nextId.current++, from: 'you', text },
      { id: nextId.current++, from: 'assistant', text: answer },
    ])
    setDraft('')
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    send(draft)
  }

  return (
    <Panel
      title={
        <span className="flex items-center gap-2">
          <MessageCircleQuestion className="size-4.5 text-primary" aria-hidden />
          Ask the career assistant
        </span>
      }
      description="Answers are generated from the numbers on this page by simple rules; no AI model is called in demo mode."
      actions={<Pill title="Rule-based answers, no AI model">Rule-based</Pill>}
      bodyClassName="space-y-4"
    >
      <div
        ref={logRef}
        role="log"
        aria-live="polite"
        aria-label="Conversation with the career assistant"
        tabIndex={0}
        className="max-h-[min(340px,40vh)] min-h-32 overflow-y-auto rounded-lg border bg-background p-3 focus-visible:outline-2"
      >
        <ul className="space-y-3">
          <Bubble from="assistant">
            {ready
              ? `Hi! Ask me about jobs and courses in ${districtLabel}. I only answer from the career paths and numbers shown on this page.`
              : loading
                ? `Loading the career paths for ${districtLabel}...`
                : `There are no career paths for ${districtLabel} to answer from right now.`}
          </Bubble>
          {messages.map((message) => (
            <Bubble key={message.id} from={message.from}>
              {message.text}
            </Bubble>
          ))}
        </ul>
      </div>

      <div>
        <p id="assistant-suggestions" className="mb-2 text-xs font-medium text-muted-foreground">
          Try a question
        </p>
        <div
          role="group"
          aria-labelledby="assistant-suggestions"
          className="flex flex-wrap gap-1.5"
        >
          {SUGGESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              disabled={!ready}
              onClick={() => send(question)}
              className="rounded-full border bg-card px-3 py-1 text-xs font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-accent focus-visible:outline-2 disabled:pointer-events-none disabled:opacity-50"
            >
              {question}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={onSubmit} className="flex gap-2">
        <label htmlFor="assistant-question" className="sr-only">
          Your question
        </label>
        <Input
          id="assistant-question"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type your question"
          autoComplete="off"
          maxLength={200}
          disabled={!ready}
          className="h-9"
        />
        <Button type="submit" className="h-9" disabled={!ready || !draft.trim()}>
          <Send aria-hidden /> Send
        </Button>
      </form>

      {messages.length > 0 && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          onClick={() => setMessages([])}
        >
          <RotateCcw aria-hidden /> Clear conversation
        </Button>
      )}
    </Panel>
  )
}
