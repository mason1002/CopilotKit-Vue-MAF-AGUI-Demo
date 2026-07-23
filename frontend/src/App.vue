<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { HttpAgent } from '@ag-ui/client'
import { Activity, Check, CircleAlert, Cpu, KeyRound, Server, ShieldCheck } from '@lucide/vue'
import { CopilotChat, CopilotKitProvider } from '@copilotkit/vue/v2'

const AGENT_BASE = import.meta.env.VITE_AGENT_URL ?? 'http://127.0.0.1:8100'
const COPILOTKIT_LICENSE_KEY = import.meta.env.VITE_COPILOTKIT_PUBLIC_LICENSE_KEY ?? ''
const AGENT_URL = `${AGENT_BASE}/agent`

type TracePhase = 'idle' | 'upstream' | 'streaming' | 'complete' | 'error'

type Health = {
  status: string
  mode: string
  agentEndpoint: string
  model: string
}

const token = ref('')
const tokenExpiresAt = ref(0)
const health = ref<Health>()
const bootError = ref('')
const authNotice = ref('')
const requestId = ref(crypto.randomUUID())
const browserStartedAt = ref<string>()
const trace = ref({
  requests: 0,
  status: null as number | null,
  events: [] as string[],
  error: '',
  requestId: null as string | null,
  startedAt: null as string | null,
  firstByteMs: null as number | null,
  firstTokenMs: null as number | null,
  completedMs: null as number | null,
  phase: 'idle' as TracePhase,
})
let pollTimer: ReturnType<typeof setInterval> | undefined
let tokenTimer: ReturnType<typeof setInterval> | undefined

const flowSteps = [
  { key: 'vue', eyebrow: 'Browser', title: 'Vue 3', detail: 'CopilotKit UI', icon: Activity },
  { key: 'agent', eyebrow: 'Agent host', title: 'Python Agent', detail: 'FastAPI · :8100', icon: Server },
  { key: 'model', eyebrow: 'In process', title: 'Local client', detail: 'Deterministic reply', icon: Cpu },
]
const activeTelemetry = computed(() => trace.value)
const hasObservedRun = computed(() => trace.value.phase !== 'idle')

function flowLink(index: number): string {
  return index === 0 ? 'AG-UI direct' : 'Agent client'
}

function beginObservedRun() {
  requestId.value = crypto.randomUUID()
  browserStartedAt.value = new Date().toISOString()
}

function nodePhase(key: string): TracePhase | 'waiting' | 'complete' | 'active' {
  const telemetry = trace.value
  if (telemetry.phase === 'idle') return 'waiting'
  if (telemetry.phase === 'error') return 'error'
  if (telemetry.phase === 'complete') return 'complete'
  if (key === 'vue') return 'complete'
  if (key === 'agent') return telemetry.firstByteMs === null ? 'active' : 'complete'
  if (key === 'model') return 'active'
  return 'waiting'
}

function nodeStatus(key: string): string {
  const phase = nodePhase(key)
  if (phase === 'waiting') return 'Waiting'
  if (phase === 'error') return 'Error'
  if (phase === 'active') return key === 'model' ? 'Streaming' : 'Forwarding'
  return 'Complete'
}

function nodeMetric(key: string): string {
  const telemetry = trace.value
  if (key === 'vue') return telemetry.requestId ? `ID ${telemetry.requestId.slice(0, 8)}` : 'No request yet'
  if (key === 'agent') return telemetry.firstByteMs === null ? 'Awaiting upstream' : `Headers ${telemetry.firstByteMs} ms`
  return telemetry.firstTokenMs === null ? 'Awaiting first token' : `First token ${telemetry.firstTokenMs} ms`
}

function connectorPhase(index: number): string {
  return nodePhase(flowSteps[index + 1]?.key ?? '')
}

async function observeDirectStream(response: Response, started: number) {
  if (!response.body) return
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const counts = new Map<string, number>()
  let pending = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    pending += decoder.decode(value, { stream: true })
    const lines = pending.split('\n')
    pending = lines.pop() ?? ''
    for (const line of lines.filter((item) => item.startsWith('data:'))) {
      try {
        const event = JSON.parse(line.slice(5).trim()).type as string
        counts.set(event, (counts.get(event) ?? 0) + 1)
        trace.value.events = [...counts].map(([name, count]) => count > 1 ? `${name} x ${count}` : name)
        if (event === 'TEXT_MESSAGE_CONTENT' && trace.value.firstTokenMs === null) {
          trace.value.firstTokenMs = Math.round(performance.now() - started)
          trace.value.phase = 'streaming'
        }
      } catch {
        counts.set('UNPARSED_EVENT', (counts.get('UNPARSED_EVENT') ?? 0) + 1)
      }
    }
  }
  trace.value.completedMs = Math.round(performance.now() - started)
  trace.value.phase = 'complete'
}

const directAgent = new HttpAgent({
  agentId: 'direct-agent',
  url: AGENT_URL,
  fetch: async (url, init) => {
    const started = performance.now()
    trace.value = {
      requests: trace.value.requests + 1,
      status: null,
      events: [],
      error: '',
      requestId: requestId.value,
      startedAt: browserStartedAt.value ?? new Date().toISOString(),
      firstByteMs: null,
      firstTokenMs: null,
      completedMs: null,
      phase: 'upstream',
    }
    try {
      const headers = new Headers(init?.headers)
      headers.set('Authorization', `Bearer ${token.value}`)
      headers.set('X-Demo-Transport', 'direct')
      headers.set('X-Demo-Request-ID', requestId.value)
      const response = await fetch(url, { ...init, headers })
      trace.value.status = response.status
      trace.value.firstByteMs = Math.round(performance.now() - started)
      void observeDirectStream(response.clone(), started)
      return response
    } catch (error) {
      trace.value.error = error instanceof Error ? error.message : String(error)
      trace.value.completedMs = Math.round(performance.now() - started)
      trace.value.phase = 'error'
      throw error
    }
  },
})

async function refreshHealth() {
  const response = await fetch(`${AGENT_BASE}/health`)
  if (!response.ok) throw new Error(`Agent health failed: HTTP ${response.status}`)
  health.value = await response.json()
}

function readTokenExpiry(value: string): number {
  const payload = value.split('.')[1]
  if (!payload) return 0
  const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
  const claims = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')))
  return Number(claims.exp ?? 0) * 1000
}

async function refreshToken() {
  const response = await fetch(`${AGENT_BASE}/demo-token`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`Demo token failed: HTTP ${response.status}`)
  const value = (await response.json()).access_token as string
  token.value = value
  tokenExpiresAt.value = readTokenExpiry(value)
}

async function onChatError(event: { error: Error }) {
  if (/401|bearer token/i.test(event.error.message)) {
    try {
      await refreshToken()
      authNotice.value = 'The demo session expired and was renewed. Please send the message again.'
      return
    } catch (error) {
      bootError.value = error instanceof Error ? error.message : String(error)
      return
    }
  }
  bootError.value = event.error.message
}

onMounted(async () => {
  try {
    await refreshToken()
    await refreshHealth()
    pollTimer = setInterval(() => void refreshHealth().catch(() => undefined), 600)
    tokenTimer = setInterval(() => {
      if (tokenExpiresAt.value - Date.now() <= 120_000) {
        void refreshToken().catch((error) => {
          bootError.value = error instanceof Error ? error.message : String(error)
        })
      }
    }, 30_000)
  } catch (error) {
    bootError.value = error instanceof Error ? error.message : String(error)
  }
})

onBeforeUnmount(() => {
  clearInterval(pollTimer)
  clearInterval(tokenTimer)
})
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div><p class="eyebrow">Direct AG-UI integration</p><h1>CopilotKit Vue → Python Agent</h1></div>
      <div class="header-actions">
        <div class="connection-pill" :class="{ 'is-online': health?.status === 'ok' }"><span class="pulse" />{{ health?.status === 'ok' ? 'Service online' : 'Connecting' }}</div>
      </div>
    </header>

    <section class="workspace">
      <section class="observability-pane" aria-label="Request observability">
        <section class="flow-stage" aria-label="Live agent request route">
      <div class="flow-stage-heading">
        <div><p class="eyebrow">Live request route</p><h2>Direct route · Local deterministic client</h2></div>
        <div class="route-state" :class="activeTelemetry.phase">
          <span class="route-state-dot" />{{ activeTelemetry.phase === 'idle' ? 'No request observed' : activeTelemetry.phase }}
        </div>
      </div>
      <div class="flow-track compact">
        <template v-for="(step, index) in flowSteps" :key="step.key">
          <article class="flow-node" :class="[`node-${step.key}`, `phase-${nodePhase(step.key)}`]">
            <div class="flow-node-top"><span class="flow-index">0{{ index + 1 }}</span><component :is="step.icon" :size="21" /></div>
            <div><small>{{ step.eyebrow }}</small><strong>{{ step.title }}</strong><p>{{ step.detail }}</p></div>
            <div class="node-observation"><span class="node-status"><i />{{ nodeStatus(step.key) }}</span><code>{{ nodeMetric(step.key) }}</code></div>
          </article>
          <div v-if="index < flowSteps.length - 1" class="flow-connector" :class="`phase-${connectorPhase(index)}`" aria-hidden="true">
            <span class="connector-label">{{ flowLink(index) }}</span>
            <span class="signal-line"><i v-if="connectorPhase(index) === 'active'" class="signal-packet" /></span>
          </div>
        </template>
      </div>
      <div class="run-facts" :class="{ empty: !hasObservedRun }">
        <span><small>Request ID</small><code>{{ activeTelemetry.requestId ?? '—' }}</code></span>
        <span><small>Started</small><strong>{{ activeTelemetry.startedAt ? new Date(activeTelemetry.startedAt).toLocaleTimeString() : '—' }}</strong></span>
        <span><small>First byte</small><strong>{{ activeTelemetry.firstByteMs === null ? '—' : `${activeTelemetry.firstByteMs} ms` }}</strong></span>
        <span><small>First token</small><strong>{{ activeTelemetry.firstTokenMs === null ? '—' : `${activeTelemetry.firstTokenMs} ms` }}</strong></span>
        <span><small>Total</small><strong>{{ activeTelemetry.completedMs === null ? '—' : `${activeTelemetry.completedMs} ms` }}</strong></span>
      </div>
        </section>

        <aside class="diagnostics" aria-label="Connection diagnostics">
        <div class="section-heading">
          <div><p class="eyebrow">Security & telemetry</p><h2>Request diagnostics</h2></div><ShieldCheck :size="20" />
        </div>
        <div class="checks">
          <div class="status-row"><ShieldCheck /><span>JWT sent directly by Vue</span><span class="status-value passed"><Check :size="14" />{{ token ? 'Ready' : 'Waiting' }}</span></div>
          <div class="status-row"><KeyRound /><span>Browser token scope</span><span class="status-value passed"><Check :size="14" />15 min</span></div>
          <div class="status-row"><Server /><span>Active model</span><span class="status-value">Local deterministic</span></div>
          <div class="status-row"><Activity /><span>Direct Agent requests</span><span class="status-value">{{ trace.requests }}</span></div>
          <div class="status-row"><Server /><span>Intermediary service</span><span class="status-value">None</span></div>
        </div>
        <div class="trace-panel">
          <div class="trace-title"><span>Latest browser trace</span><span class="http-status">{{ trace.status ? `HTTP ${trace.status}` : 'Idle' }}</span></div>
          <code>{{ AGENT_URL }}</code>
          <div class="event-stream event-rail">
            <span v-for="(event, index) in trace.events" :key="event"><i /> <b>{{ String(index + 1).padStart(2, '0') }}</b>{{ event }}</span>
            <p v-if="!trace.events.length">Send a message to capture AG-UI events.</p>
          </div>
        </div>
        <div class="boundary-note"><CircleAlert :size="18" /><p>The browser calls the Python Agent directly. The API owns CORS, authentication, authorization, rate limits, and audit controls.</p></div>
        </aside>
      </section>

      <section class="chat-panel" aria-label="Vue CopilotKit chat">
        <div class="chat-header">
          <div><p class="eyebrow">Live test surface</p><h2>Vue CopilotChat</h2></div>
          <div class="endpoint-label"><span>Direct URL</span><code>/agent</code></div>
        </div>
        <div class="chat-host">
          <div v-if="bootError" class="empty-state is-error"><CircleAlert /><h3>Connection error</h3><p>{{ bootError }}</p></div>
          <CopilotKitProvider v-else-if="token" :self-managed-agents="{ 'direct-agent': directAgent }" :public-license-key="COPILOTKIT_LICENSE_KEY || undefined" :show-dev-console="false" :on-error="onChatError">
            <div v-if="authNotice" class="auth-notice" role="status">{{ authNotice }}</div>
            <CopilotChat agent-id="direct-agent" :welcome-screen="true" auto-scroll="pin-to-send" @submit-message="beginObservedRun" />
          </CopilotKitProvider>
          <div v-else class="empty-state"><div class="loader" /><h3>Preparing authenticated session</h3><p>Load a short-lived local demo token.</p></div>
        </div>
      </section>
    </section>
    <footer><span>Frontend: Vue 3</span><span>Transport: Direct AG-UI</span><span>Model: Local deterministic</span></footer>
  </main>
</template>
