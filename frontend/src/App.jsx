import { useState, useRef, useEffect, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || ''

// ── Helpers ─────────────────────────────────────────────────────────────────
function captureFrame(videoEl) {
  if (!videoEl || !videoEl.videoWidth) return null
  const canvas = document.createElement('canvas')
  canvas.width = videoEl.videoWidth
  canvas.height = videoEl.videoHeight
  canvas.getContext('2d').drawImage(videoEl, 0, 0)
  const dataUrl = canvas.toDataURL('image/jpeg', 0.75)
  return dataUrl.split(',')[1] // base64 only
}

async function askAPI(question, screenshot, history) {
  const res = await fetch(`${API_BASE}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, screenshot, history }),
  })
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

function speak(text) {
  if (!text || !window.speechSynthesis) return
  speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text.slice(0, 280))
  u.rate = 1.05
  const voices = speechSynthesis.getVoices()
  const best = voices.find(v => /Google.*English|Natural|Premium/i.test(v.name))
  if (best) u.voice = best
  speechSynthesis.speak(u)
}

// ── Sub-components ────────────────────────────────────────────────────────────
function StatusBadge({ state }) {
  const colors = { idle: '#3d4160', live: '#4ade80', processing: '#fbbf24' }
  const dot = colors[state] || colors.idle
  return (
    <div className="status-badge">
      <span className="dot" style={{
        background: dot,
        boxShadow: state !== 'idle' ? `0 0 8px ${dot}` : 'none',
        animation: state !== 'idle' ? 'pulse 2s infinite' : 'none'
      }} />
      {state}
    </div>
  )
}

function ThinkingBubble() {
  return (
    <div className="msg">
      <div className="avatar ai">AI</div>
      <div className="msg-body">
        <div className="msg-name">reality copilot</div>
        <div className="thinking">
          <span /><span /><span />
          analyzing...
        </div>
      </div>
    </div>
  )
}

function AiMessage({ text, steps, uiNote }) {
  return (
    <div className="msg">
      <div className="avatar ai">AI</div>
      <div className="msg-body">
        <div className="msg-name">reality copilot</div>
        {text && <p className="msg-text">{text}</p>}
        {steps?.length > 0 && (
          <div className="steps">
            {steps.map((s, i) => (
              <div key={i} className="step">
                <span className="step-num">{i + 1}</span>
                <span>{s}</span>
              </div>
            ))}
          </div>
        )}
        {uiNote && (
          <div className="ui-note">
            <span>👆</span> {uiNote}
          </div>
        )}
      </div>
    </div>
  )
}

function UserMessage({ text, hasScreen }) {
  return (
    <div className="msg user-msg">
      <div className="msg-body" style={{ alignItems: 'flex-end' }}>
        <div className="msg-name" style={{ textAlign: 'right' }}>you</div>
        <p className="msg-text user-text">{text}</p>
        {hasScreen && <div className="screen-pill">📷 Screen captured</div>}
      </div>
      <div className="avatar user">U</div>
    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [status, setStatus] = useState('idle')
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [isListening, setIsListening] = useState(false)
  const [isSharing, setIsSharing] = useState(false)
  const [analysisNote, setAnalysisNote] = useState('')

  const videoRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const recognitionRef = useRef(null)
  const messagesEndRef = useRef(null)
  const historyRef = useRef([])
  const lastScreenRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Screen sharing ──────────────────────────────────────────────────────────
  const startShare = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 5, width: { ideal: 1280 } },
        audio: false,
      })
      mediaStreamRef.current = stream
      videoRef.current.srcObject = stream
      setIsSharing(true)
      setStatus('live')
      stream.getVideoTracks()[0].onended = stopShare

      setTimeout(() => {
        lastScreenRef.current = captureFrame(videoRef.current)
      }, 1200)
    } catch (e) {
      if (e.name !== 'NotAllowedError') {
        alert('Screen share failed. Try a different browser or check permissions.')
      }
    }
  }, [])

  const stopShare = useCallback(() => {
    mediaStreamRef.current?.getTracks().forEach(t => t.stop())
    mediaStreamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setIsSharing(false)
    setStatus('idle')
    lastScreenRef.current = null
  }, [])

  // ── Voice input ─────────────────────────────────────────────────────────────
  const setupRecognition = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return null
    const r = new SR()
    r.continuous = false
    r.interimResults = true
    r.lang = 'en-US'
    r.onresult = e => {
      const t = Array.from(e.results).map(r => r[0].transcript).join('')
      setInputText(t)
      if (e.results[e.results.length - 1].isFinal) {
        stopListening()
        setTimeout(() => sendMessage(t), 100)
      }
    }
    r.onerror = () => stopListening()
    r.onend = () => stopListening()
    return r
  }, [])

  const startListening = () => {
    if (!recognitionRef.current) recognitionRef.current = setupRecognition()
    if (!recognitionRef.current) return alert('Voice not supported in this browser')
    setIsListening(true)
    recognitionRef.current.start()
  }

  const stopListening = () => {
    setIsListening(false)
    try { recognitionRef.current?.stop() } catch (_) {}
  }

  // ── Send message ────────────────────────────────────────────────────────────
  const sendMessage = useCallback(async (overrideText) => {
    const text = (overrideText ?? inputText).trim()
    if (!text) return

    setInputText('')
    const screenshot = captureFrame(videoRef.current)
    lastScreenRef.current = screenshot

    setMessages(m => [...m, { type: 'user', text, hasScreen: !!screenshot }])
    setMessages(m => [...m, { type: 'thinking' }])
    setStatus('processing')

    try {
      const resp = await askAPI(text, screenshot, historyRef.current.slice(-6))

      historyRef.current.push({ role: 'user', content: text })
      historyRef.current.push({ role: 'assistant', content: resp.text })

      setMessages(m => {
        const filtered = m.filter(x => x.type !== 'thinking')
        return [...filtered, { type: 'ai', ...resp }]
      })

      if (resp.ui_note) {
        setAnalysisNote(resp.ui_note)
        setTimeout(() => setAnalysisNote(''), 6000)
      }

      speak(resp.summary || resp.text)
    } catch (err) {
      setMessages(m => m.filter(x => x.type !== 'thinking').concat([{
        type: 'ai',
        text: `Error: ${err.message}. Make sure the backend is running and GEMINI_API_KEY is set.`,
        steps: [],
      }]))
    }

    setStatus(isSharing ? 'live' : 'idle')
  }, [inputText, isSharing])

  const handleKey = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="app">
      {/* Header */}
      <header>
        <div className="logo">
          <div className="logo-icon">👁</div>
          <span className="logo-text">Reality<span>Copilot</span></span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <StatusBadge state={status} />
        </div>
      </header>

      {/* Main */}
      <main>
        {/* Screen panel */}
        <div className="screen-panel">
          <div className="panel-header">
            <span className="label">screen feed</span>
            {isSharing && (
              <div className="live-indicator">
                <span className="dot" style={{ background: '#4ade80', boxShadow: '0 0 6px #4ade80', animation: 'pulse 2s infinite' }} />
                LIVE
              </div>
            )}
          </div>

          <div className="screen-box">
            {!isSharing && (
              <div className="screen-idle">
                <div className="idle-icon">🖥</div>
                <h2>No screen shared</h2>
                <p>Share your screen so the AI can see what you're working on and guide you.</p>
                <button className="btn btn-primary" onClick={startShare}>
                  ⊹ Share Screen
                </button>
              </div>
            )}

            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              style={{ display: isSharing ? 'block' : 'none', width: '100%', height: '100%', objectFit: 'contain' }}
            />

            {analysisNote && (
              <div className="analysis-overlay">
                <span>👆 {analysisNote}</span>
              </div>
            )}
          </div>

          <div className="screen-actions">
            {!isSharing ? (
              <button className="btn btn-primary" onClick={startShare}>⊹ Share Screen</button>
            ) : (
              <>
                <button className="btn" onClick={() => { lastScreenRef.current = captureFrame(videoRef.current) }}>
                  📷 Capture Now
                </button>
                <button className="btn btn-danger" onClick={stopShare}>✕ Stop</button>
                <span className="label">Auto-captures every question</span>
              </>
            )}
          </div>
        </div>

        {/* Chat panel */}
        <div className="chat-panel">
          <div className="panel-header">
            <span className="label">ai assistant</span>
            <span className="model-badge">gemini-2.5-flash</span>
          </div>

          <div className="messages">
            {messages.length === 0 && (
              <div className="chat-empty">
                <div style={{ fontSize: 32, opacity: 0.3 }}>💬</div>
                <p>Share your screen, then ask me anything about what you're working on.</p>
              </div>
            )}
            {messages.map((msg, i) => {
              if (msg.type === 'thinking') return <ThinkingBubble key={i} />
              if (msg.type === 'user') return <UserMessage key={i} text={msg.text} hasScreen={msg.hasScreen} />
              if (msg.type === 'ai') return <AiMessage key={i} text={msg.text} steps={msg.steps} uiNote={msg.ui_note} />
              return null
            })}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <div className="input-row">
              <button
                className={`mic-btn${isListening ? ' listening' : ''}`}
                onClick={isListening ? stopListening : startListening}
                title="Click to speak"
              >
                🎤
              </button>
              <div className="input-wrap">
                <textarea
                  className="text-input"
                  value={inputText}
                  onChange={e => setInputText(e.target.value)}
                  onKeyDown={handleKey}
                  placeholder={isListening ? 'Listening...' : 'Ask about your screen...'}
                  rows={1}
                />
                <button className="send-btn" onClick={() => sendMessage()}>↑</button>
              </div>
            </div>
            <div className="hints">
              {['How do I do this?', 'Explain what I see', 'What\'s next?', 'Fix this error'].map(h => (
                <button key={h} className="hint" onClick={() => setInputText(h)}>{h}</button>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
