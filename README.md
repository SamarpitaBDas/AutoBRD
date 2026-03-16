# 👁 Reality Copilot
### AI that sees your screen and guides you in real time

**Hackathon project** — Google Gemini API · Multimodal Vision + Voice · Cloud Run

---

## What it does

Share your screen. Ask anything. The AI sees your UI and gives step-by-step instructions with voice output.

**Example:**
> "How do I add a pivot table?" → AI sees your Excel, responds with exact steps + highlights the button

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | React + Vite + Web Speech API |
| Backend | Python FastAPI |
| AI | Gemini 2.0 Flash (multimodal) |
| Deployment | Google Cloud Run |

---

## Quick Start (Local Dev)

### Prerequisites
- Python 3.12+
- Node.js 18+
- A [Gemini API key](https://aistudio.google.com/app/apikey)

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
export GEMINI_API_KEY="your_key_here"
python main.py
# → Running on http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# → Running on http://localhost:5173
```

### 3. Open app

1. Go to `http://localhost:5173`
2. Click **Share Screen**
3. Select the window/tab you're working in
4. Ask your question by text or voice

---

## Deploy to Google Cloud Run

### Prerequisites
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed & authenticated
- A GCP project with billing enabled
- Gemini API key

### One-command deploy

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh YOUR_GCP_PROJECT_ID YOUR_GEMINI_API_KEY
```

This script:
1. Builds the React frontend
2. Bundles it into the Docker image
3. Deploys to Cloud Run (auto-scales to 0 when idle = free when not in use)

### Manual deploy (step by step)

```bash
# Build frontend into backend/dist
cd frontend && npm run build && cd ..

# Submit build to Cloud Build
cd backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT/reality-copilot .

# Deploy
gcloud run deploy reality-copilot \
  --image gcr.io/YOUR_PROJECT/reality-copilot \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=YOUR_KEY
```

---

## API Reference

### `POST /api/ask`

```json
{
  "question": "How do I export this as PNG?",
  "screenshot": "<base64 JPEG>",
  "history": [
    { "role": "user", "content": "previous message" },
    { "role": "assistant", "content": "previous reply" }
  ]
}
```

**Response:**
```json
{
  "text": "To export as PNG, go to File > Export.",
  "steps": [
    "Click File in the top menu",
    "Select Export or Save As",
    "Choose PNG from the format dropdown",
    "Click Export"
  ],
  "summary": "Go to File, then Export, select PNG.",
  "ui_note": "Click the blue Export button in the top-right corner",
  "success": true
}
```

---

## How multimodal works

```
User asks question
        │
        ▼
Capture video frame (canvas.toDataURL)
        │
        ▼
Send to Gemini 2.0 Flash:
  - base64 JPEG screenshot
  - user question
  - conversation history
  - system prompt (UI assistant persona)
        │
        ▼
Gemini returns structured JSON
  (text + steps + ui_note)
        │
        ▼
Render in chat + speak via Web Speech API
```

---

## Project structure

```
reality-copilot/
├── backend/
│   ├── main.py          # FastAPI app + Gemini integration
│   ├── requirements.txt
│   └── Dockerfile       # Cloud Run container
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # Main React component
│   │   └── index.css    # Styles
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── deploy/
    └── deploy.sh        # One-command Cloud Run deploy
```

---

## Judging criteria alignment

| Criterion | How we meet it |
|-----------|----------------|
| **Innovation (40%)** | Live screen-watching AI assistant — no tutorial, no manual |
| **Technical (30%)** | Multimodal vision + voice input + TTS output + Cloud Run |
| **Demo (30%)** | Share screen → ask → AI guides you. Visually impressive in 4 min |

**Multimodal checklist:**
- 👁 **See** — Gemini receives screenshot frames via vision API
- 🎤 **Hear** — Web Speech API captures voice input
- 🔊 **Speak** — SpeechSynthesis speaks the AI response aloud

---

## Demo script (4 minutes)

1. **(0:00)** Open the app, show clean UI
2. **(0:20)** "Let me share my screen" → share Excel with some data
3. **(0:40)** Ask by voice: *"How do I add a chart to this data?"*
4. **(1:00)** AI responds with steps + speaks them aloud
5. **(1:30)** Follow the steps, ask follow-up: *"Now how do I change the colors?"*
6. **(2:00)** Switch to VS Code, show a Python error
7. **(2:15)** Ask: *"Can you explain this error?"*
8. **(2:35)** AI identifies the error, gives fix steps
9. **(3:00)** Show Cloud Run deployment running
10. **(3:30)** Wrap up with architecture slide

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | From [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `PORT` | No | Server port (default 8080 for Cloud Run) |

---

Built for Google Gemini Hackathon 2025 · [MIT License](LICENSE)
