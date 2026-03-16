#!/bin/bash
# Reality Copilot — Deploy to Google Cloud Run
# Usage: ./deploy.sh YOUR_PROJECT_ID YOUR_GEMINI_API_KEY

set -e

PROJECT_ID=${1:-"your-gcp-project"}
GEMINI_API_KEY=${2:-""}
REGION="us-central1"
SERVICE_NAME="reality-copilot"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying Reality Copilot to Cloud Run"
echo "   Project: $PROJECT_ID"
echo "   Region:  $REGION"
echo ""

# 1. Build frontend
echo "📦 Building frontend..."
cd frontend
npm install
npm run build
cd ..

# 2. Build & push Docker image
echo "🐳 Building Docker image..."
cd backend
gcloud builds submit --tag "$IMAGE" .
cd ..

# 3. Deploy to Cloud Run
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "GEMINI_API_KEY=$GEMINI_API_KEY" \
  --project "$PROJECT_ID"

echo ""
echo "✅ Deployed! Getting URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --platform managed \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format 'value(status.url)')

echo ""
echo "🌐 Reality Copilot is live at: $SERVICE_URL"
echo ""
echo "📝 Next steps:"
echo "   1. Open $SERVICE_URL in Chrome or Edge"
echo "   2. Click 'Share Screen'"
echo "   3. Ask anything about your screen!"
