"""
Reality Copilot - FastAPI Backend
Powered by Google Gemini 2.0 Flash (multimodal)
"""

import os
import base64
import json
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.0-flash-exp"  # or "gemini-1.5-flash"

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set — AI responses will be mocked")

genai.configure(api_key=GEMINI_API_KEY)

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="Reality Copilot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────────────
class ConversationTurn(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    question: str
    screenshot: Optional[str] = None      # base64 JPEG, no data URI prefix
    history: list[ConversationTurn] = []

class AskResponse(BaseModel):
    text: str
    steps: list[str] = []
    summary: str = ""
    ui_note: str = ""
    success: bool = True

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Reality Copilot — an AI assistant that watches users' screens and gives step-by-step guidance.

Your personality:
- Clear, concise, action-oriented. No fluff.
- Use numbered steps for tasks. Each step: one action.
- If you see UI elements (buttons, menus, dialogs), reference them by name/color.
- If you spot an error, explain it and give the fix first.
- Max 3-4 sentences for the main explanation, then steps.

Response format — ALWAYS return valid JSON with this structure:
{
  "text": "brief explanation (1-3 sentences)",
  "steps": ["step 1 action", "step 2 action", "step 3 action"],
  "summary": "one sentence spoken summary for TTS",
  "ui_note": "optional: if you see a specific UI element to click (e.g. 'Click the blue Export button in the top right')"
}

If there's no screenshot or it's unclear:
- Still answer based on the question
- Keep steps generic but helpful
- Set ui_note to ""

Rules:
- steps array: empty [] if no step-by-step needed, max 6 steps
- ui_note: only if you identify a SPECIFIC UI element the user should interact with next
- summary: always present, used for text-to-speech — no markdown, plain prose
- Respond ONLY with JSON, no preamble, no markdown fences"""

# ── Gemini helper ─────────────────────────────────────────────────────────────
def build_gemini_parts(question: str, screenshot_b64: Optional[str], history: list[ConversationTurn]):
    """Build the content parts for Gemini API call."""
    parts = []

    # Add screenshot if present
    if screenshot_b64:
        try:
            image_bytes = base64.b64decode(screenshot_b64)
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": screenshot_b64
                }
            })
        except Exception as e:
            logger.warning(f"Could not decode screenshot: {e}")

    # Build conversation context
    history_text = ""
    if history:
        history_text = "\n\nConversation context:\n"
        for turn in history[-4:]:  # last 4 turns
            history_text += f"{turn.role.upper()}: {turn.content}\n"

    parts.append(f"{history_text}\n\nUser question: {question}")

    return parts

async def call_gemini(request: AskRequest) -> AskResponse:
    """Call Gemini API with multimodal input."""

    if not GEMINI_API_KEY:
        return mock_response(request.question)

    try:
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            generation_config={
                "temperature": 0.3,
                "top_p": 0.8,
                "max_output_tokens": 1024,
                "response_mime_type": "application/json",
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

        parts = build_gemini_parts(request.question, request.screenshot, request.history)
        response = model.generate_content(parts)

        raw_text = response.text.strip()

        # Strip any accidental markdown fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        parsed = json.loads(raw_text)

        return AskResponse(
            text=parsed.get("text", ""),
            steps=parsed.get("steps", []),
            summary=parsed.get("summary", parsed.get("text", "")),
            ui_note=parsed.get("ui_note", ""),
            success=True
        )

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw: {raw_text[:200]}")
        return AskResponse(
            text=raw_text[:500],
            steps=[],
            summary=raw_text[:150],
            ui_note="",
            success=True
        )
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def mock_response(question: str) -> AskResponse:
    """Fallback mock response when no API key is set."""
    q = question.lower()

    if "pivot" in q or "excel" in q:
        return AskResponse(
            text="I can see you're working in Excel. Here's how to add a pivot table.",
            steps=[
                "Select your data range (click and drag)",
                "Click the 'Insert' tab in the top menu bar",
                "Click 'PivotTable' — it's the first button on the left",
                "In the dialog, confirm the range and choose 'New Worksheet'",
                "Click OK — your pivot table canvas will appear"
            ],
            summary="To add a pivot table, select your data, go to Insert, and click PivotTable.",
            ui_note="Click the blue 'Insert' tab at the top of the ribbon",
            success=True
        )
    elif "export" in q or "png" in q or "save" in q:
        return AskResponse(
            text="I can see you want to export. The exact steps depend on your app, but here's the general approach.",
            steps=[
                "Go to File menu (top-left) or press Ctrl+Shift+E",
                "Look for 'Export' or 'Save As'",
                "Select PNG as the file format",
                "Choose your export location",
                "Click Export or Save"
            ],
            summary="Go to File, then Export, select PNG format, and save to your chosen location.",
            ui_note="",
            success=True
        )
    else:
        return AskResponse(
            text=f"I'm analyzing your screen for '{question}'. Set your GEMINI_API_KEY environment variable for real AI responses.",
            steps=[
                "Make sure GEMINI_API_KEY is set in your environment",
                "Restart the backend server",
                "Try your question again with screen sharing active"
            ],
            summary="Set your Gemini API key and restart the server for real AI assistance.",
            ui_note="",
            success=True
        )

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "api_key_set": bool(GEMINI_API_KEY)
    }

@app.post("/api/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """Main endpoint: receive question + optional screenshot, return AI guidance."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    return await call_gemini(request)

# ── Serve frontend in production ───────────────────────────────────────────────
frontend_dist = os.path.join(os.path.dirname(__file__), "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        index = os.path.join(frontend_dist, "index.html")
        return FileResponse(index)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
