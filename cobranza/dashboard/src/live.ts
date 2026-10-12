import { useConversation } from '@elevenlabs/react'
import { useCallback, useRef, useState } from 'react'
import type { Customer } from './api'
import type { AgentState } from '@/components/ui/orb'

type NewLine = { kind: 'user' | 'agent'; text: string } | { kind: 'tool'; tool: string; ok: boolean | null }
export type Line = NewLine & { id: number }

export function useLiveCall(agentId: string | undefined, onEnded: () => void) {
  const [lines, setLines] = useState<Line[]>([])
  const [caller, setCaller] = useState<Customer | null>(null)
  const [pendingTools, setPendingTools] = useState(0)
  const [error, setError] = useState('')
  const mic = useRef<MediaStream | null>(null)
  const nextId = useRef(0)

  const push = (line: NewLine) => setLines((all) => [...all, { ...line, id: nextId.current++ }])

  const releaseMic = () => {
    mic.current?.getTracks().forEach((t) => t.stop())
    mic.current = null
  }

  const conversation = useConversation({
    onMessage: ({ role, message }) => push({ kind: role === 'user' ? 'user' : 'agent', text: message }),
    onAgentToolRequest: ({ tool_name }) => {
      setPendingTools((n) => n + 1)
      push({ kind: 'tool', tool: tool_name, ok: null })
    },
    onAgentToolResponse: ({ tool_name, is_error }) => {
      setPendingTools((n) => Math.max(0, n - 1))
      setLines((all) => {
        const i = all.findLastIndex((l) => l.kind === 'tool' && l.tool === tool_name && l.ok === null)
        if (i < 0) return all
        const next = [...all]
        next[i] = { ...all[i], kind: 'tool', tool: tool_name, ok: !is_error }
        return next
      })
    },
    onError: (message) => setError(message),
    onDisconnect: () => {
      releaseMic()
      setPendingTools(0)
      onEnded()
    },
  })

  const start = useCallback(
    async (as: Customer | null = null) => {
      if (!agentId) return
      setCaller(as)
      setLines([])
      setError('')
      try {
        mic.current = await navigator.mediaDevices.getUserMedia({ audio: true })
      } catch {
        setError('Sin acceso al micrófono. Permítelo en el navegador para llamar.')
        return
      }
      conversation.startSession({ agentId, connectionType: 'webrtc' })
    },
    [agentId, conversation],
  )

  const { status, isSpeaking, isMuted } = conversation
  const agentState: AgentState =
    status === 'connecting' || pendingTools > 0 ? 'thinking'
    : status !== 'connected' ? null
    : isSpeaking ? 'talking'
    : 'listening'

  return {
    status,
    agentState,
    lines,
    caller,
    error,
    isMuted,
    start,
    end: conversation.endSession,
    toggleMute: () => conversation.setMuted(!isMuted),
    getInputVolume: conversation.getInputVolume,
    getOutputVolume: conversation.getOutputVolume,
  }
}

export type LiveCall = ReturnType<typeof useLiveCall>
