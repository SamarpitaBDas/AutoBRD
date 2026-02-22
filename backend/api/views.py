from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.http import FileResponse
from django.conf import settings
from django.contrib.auth.models import User
import os
import csv
import threading
from email import message_from_string

from .models import (
    Project, DataSource, ExtractedRequirement,
    BRDDocument, ConflictDetection, EditHistory
)
from .serializers import (
    ProjectSerializer, DataSourceSerializer,
    ExtractedRequirementSerializer, BRDDocumentSerializer,
    ConflictDetectionSerializer, EditHistorySerializer,
    BRDGenerationRequestSerializer, EditRequestSerializer
)
from ml_models.brd_generator import BRDGenerator
from ml_models.requirement_extractor import RequirementExtractor
from ml_models.conflict_detector import ConflictDetector
from integrations.gmail_integration import GmailIntegration
from integrations.slack_integration import SlackIntegration


# ── Shared loader state so the frontend can poll progress ─────────────────────
_load_status = {
    "running": False,
    "total": 0,
    "imported": 0,
    "requirements": 0,
    "skipped": 0,
    "error": None,
    "done": False,
}


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by('-created_at')
    serializer_class = ProjectSerializer

    @action(detail=True, methods=['post'])
    def sync_data_sources(self, request, pk=None):
        """Sync data from connected sources"""
        project = self.get_object()
        product_topic = request.data.get('product_topic', None)

        if request.data.get('sync_gmail'):
            gmail = GmailIntegration()
            emails = gmail.fetch_emails(query=request.data.get('gmail_query', ''))
            for email in emails:
                DataSource.objects.create(
                    project=project,
                    source_type='email',
                    source_identifier=email['id'],
                    raw_content=email['body'],
                    metadata=email['metadata']
                )

        if request.data.get('sync_slack'):
            slack = SlackIntegration()
            messages = slack.fetch_messages(
                channel=request.data.get('slack_channel'),
                days=request.data.get('days', 30),
                product_topic=product_topic,       # ← multi-product filter
            )
            for message in messages:
                DataSource.objects.create(
                    project=project,
                    source_type='slack',
                    source_identifier=message['ts'],
                    raw_content=message['text'],
                    metadata=str(message['metadata'])
                )

        return Response({'status': 'Data sources synced'})

    @action(detail=False, methods=['post'])
    def load_dataset(self, request):
        """
        Load the Enron email CSV dataset into a project.

        POST body (JSON):
            project_name  : str  — project to create/reuse
            product_topic : str  — optional topic filter  (e.g. "energy trading")
            limit         : int  — max emails to process  (default 300)
            csv_filename  : str  — filename inside dataset/ folder (default emails.csv)
        """
        global _load_status

        if _load_status["running"]:
            return Response(
                {"status": "already_running", "progress": _load_status},
                status=status.HTTP_409_CONFLICT,
            )

        project_name  = request.data.get("project_name", "Enron Dataset Project")
        product_topic = request.data.get("product_topic", None)
        limit         = int(request.data.get("limit", 300))
        csv_filename  = request.data.get("csv_filename", "emails.csv")

        # Resolve the CSV path — dataset/ folder sits next to manage.py
        csv_path = os.path.join(settings.BASE_DIR, "dataset", csv_filename)
        if not os.path.exists(csv_path):
            return Response(
                {"error": f"CSV not found at {csv_path}. "
                           "Put your CSV in backend/dataset/emails.csv"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create project
        user, _ = User.objects.get_or_create(username="dataset_loader")
        project, _ = Project.objects.get_or_create(
            name=project_name,
            defaults={
                "description": f"Loaded from Enron dataset. Topic: {product_topic or 'general'}",
                "user": user,
            },
        )

        # Reset status
        _load_status = {
            "running": True,
            "total": 0,
            "imported": 0,
            "requirements": 0,
            "skipped": 0,
            "error": None,
            "done": False,
            "project_id": project.id,
        }

        # Run in background thread so the HTTP response returns immediately
        thread = threading.Thread(
            target=_run_dataset_loader,
            args=(csv_path, project, product_topic, limit),
            daemon=True,
        )
        thread.start()

        return Response({
            "status": "started",
            "project_id": project.id,
            "csv_path": csv_path,
            "limit": limit,
            "product_topic": product_topic,
            "message": "Dataset loading started in background. Poll /api/projects/dataset_status/ for progress.",
        })

    @action(detail=False, methods=['get'])
    def dataset_status(self, request):
        """Poll this endpoint to check CSV loading progress."""
        return Response(_load_status)


class DataSourceViewSet(viewsets.ModelViewSet):
    queryset = DataSource.objects.all().order_by('-created_at')
    serializer_class = DataSourceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    @action(detail=False, methods=['post'])
    def upload_document(self, request):
        """Upload and process a document"""
        project_id = request.data.get('project_id')
        file = request.FILES.get('file')

        if not file or not project_id:
            return Response(
                {'error': 'Missing file or project_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        content = file.read().decode('utf-8', errors='ignore')
        data_source = DataSource.objects.create(
            project_id=project_id,
            source_type='document',
            source_identifier=file.name,
            raw_content=content,
            metadata=str({'filename': file.name, 'size': file.size})
        )
        return Response(DataSourceSerializer(data_source).data)

    @action(detail=False, methods=['post'])
    def process_sources(self, request):
        """Extract requirements from data sources using ML"""
        project_id  = request.data.get('project_id')
        product_topic = request.data.get('product_topic', None)
        sources = DataSource.objects.filter(project_id=project_id)

        extractor = RequirementExtractor()
        req_count = 0

        for source in sources:
            if product_topic:
                is_relevant, score = extractor.filter_for_product(
                    source.raw_content, product_topic
                )
            else:
                is_relevant, score = extractor.filter_noise(source.raw_content)

            source.is_relevant = is_relevant
            source.relevance_score = score
            source.save()

            if is_relevant:
                text = (
                    extractor.get_product_sentences(source.raw_content, product_topic)
                    if product_topic
                    else source.raw_content
                )
                requirements = extractor.extract_requirements(text, source)
                for req in requirements:
                    ExtractedRequirement.objects.create(
                        project_id=project_id,
                        data_source=source,
                        **req
                    )
                    req_count += 1

        return Response({'status': 'Requirements extracted', 'requirements_found': req_count})


class ExtractedRequirementViewSet(viewsets.ModelViewSet):
    queryset = ExtractedRequirement.objects.all().order_by('-created_at')
    serializer_class = ExtractedRequirementSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset


class BRDDocumentViewSet(viewsets.ModelViewSet):
    queryset = BRDDocument.objects.all().order_by('-created_at')
    serializer_class = BRDDocumentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate BRD document from project requirements"""
        serializer = BRDGenerationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        project = Project.objects.get(id=data['project_id'])

        generator = BRDGenerator()
        brd_content = generator.generate_brd(
            project=project,
            include_conflicts=data['include_conflicts'],
            include_traceability=data['include_traceability'],
            include_sentiment=data['include_sentiment'],
        )

        brd = BRDDocument.objects.create(
            project=project,
            title=brd_content['title'],
            executive_summary=brd_content['executive_summary'],
            business_objectives=brd_content['business_objectives'],
            stakeholder_analysis=brd_content['stakeholder_analysis'],
            functional_requirements=brd_content['functional_requirements'],
            non_functional_requirements=brd_content['non_functional_requirements'],
            assumptions=brd_content['assumptions'],
            success_metrics=brd_content['success_metrics'],
            timeline=brd_content['timeline'],
            conflict_analysis=brd_content.get('conflict_analysis', ''),
            traceability_matrix=str(brd_content.get('traceability_matrix', {})),
            sentiment_analysis=str(brd_content.get('sentiment_analysis', {})),
        )

        file_path = generator.generate_document_file(brd)
        brd.file_path = file_path
        brd.save()

        return Response(BRDDocumentSerializer(brd).data)

    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        """Edit BRD document with natural language instruction"""
        brd = self.get_object()
        serializer = EditRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        section = data['section']
        instruction = data['edit_instruction']
        previous_content = getattr(brd, section, '')

        generator = BRDGenerator()
        new_content = generator.apply_edit(previous_content, instruction)

        setattr(brd, section, new_content)
        brd.version += 1
        brd.save()

        EditHistory.objects.create(
            brd_document=brd,
            section=section,
            edit_request=instruction,
            previous_content=previous_content,
            new_content=new_content,
        )

        return Response(BRDDocumentSerializer(brd).data)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download BRD as a .docx file"""
        brd = self.get_object()
        if not brd.file_path or not os.path.exists(brd.file_path):
            generator = BRDGenerator()
            file_path = generator.generate_document_file(brd)
            brd.file_path = file_path
            brd.save()

        return FileResponse(
            open(brd.file_path, 'rb'),
            as_attachment=True,
            filename=f"BRD_{brd.project.name}_v{brd.version}.docx",
        )


class ConflictDetectionViewSet(viewsets.ModelViewSet):
    queryset = ConflictDetection.objects.all().order_by('-created_at')
    serializer_class = ConflictDetectionSerializer

    @action(detail=False, methods=['post'])
    def detect_conflicts(self, request):
        """Detect conflicts between extracted requirements"""
        project_id = request.data.get('project_id')
        requirements = ExtractedRequirement.objects.filter(project_id=project_id)

        detector = ConflictDetector()
        conflicts = detector.detect_conflicts(list(requirements))

        for conflict in conflicts:
            ConflictDetection.objects.create(project_id=project_id, **conflict)

        return Response({'status': f'{len(conflicts)} conflicts detected'})


@api_view(['GET'])
def health_check(request):
    return Response({'status': 'healthy'})


# ─────────────────────────────────────────────────────────────────────────────
# Background dataset loader — runs in a thread, updates _load_status
# ─────────────────────────────────────────────────────────────────────────────

def _parse_email_body(raw: str) -> dict:
    """Parse raw email string into headers + body dict."""
    try:
        msg = message_from_string(raw)
        body = msg.get_payload()
        if isinstance(body, list):
            body = "\n".join(
                p.get_payload(decode=True).decode("utf-8", errors="replace")
                for p in body
                if p.get_content_type() == "text/plain"
            )
        elif isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        return {
            "from": msg.get("From", ""),
            "to":   msg.get("To", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", ""),
            "body": (body or "").strip(),
        }
    except Exception:
        return {"from": "", "to": "", "subject": "", "date": "", "body": raw}


def _run_dataset_loader(csv_path, project, product_topic, limit):
    """
    Reads the Enron CSV, creates DataSource + ExtractedRequirement records.
    Runs in a background thread and updates _load_status for polling.
    """
    global _load_status
    try:
        extractor = RequirementExtractor()

        with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            total = imported = req_count = skipped = 0

            for row in reader:
                if total >= limit:
                    break
                total += 1

                file_id = row.get("file", "").strip()
                raw_msg = row.get("message", "").strip()
                if not raw_msg:
                    skipped += 1
                    continue

                parsed = _parse_email_body(raw_msg)
                body = parsed["body"]

                if len(body.split()) < 5:
                    skipped += 1
                    continue

                # Relevance check
                if product_topic:
                    is_relevant, score = extractor.filter_for_product(body, product_topic)
                else:
                    is_relevant, score = extractor.filter_noise(body)

                if not is_relevant and score < 0.2:
                    skipped += 1
                    continue

                # Save DataSource
                ds = DataSource.objects.create(
                    project=project,
                    source_type="email",
                    source_identifier=file_id or f"row_{total}",
                    raw_content=raw_msg,
                    processed_content=body,
                    is_relevant=is_relevant,
                    relevance_score=score,
                    metadata=str({
                        "from":    parsed["from"],
                        "to":      parsed["to"],
                        "subject": parsed["subject"],
                        "date":    parsed["date"],
                        "dataset": "enron",
                    })
                )

                imported += 1

                # Extract requirements from relevant sources
                if is_relevant:
                    text = (
                        extractor.get_product_sentences(body, product_topic)
                        if product_topic else body
                    )
                    reqs = extractor.extract_requirements(text, ds)
                    for req in reqs:
                        ExtractedRequirement.objects.create(
                            project=project,
                            data_source=ds,
                            **req,
                        )
                        req_count += 1

                # Update progress every 10 rows
                if total % 10 == 0:
                    _load_status.update({
                        "total": total,
                        "imported": imported,
                        "requirements": req_count,
                        "skipped": skipped,
                    })

        _load_status.update({
            "running": False,
            "done": True,
            "total": total,
            "imported": imported,
            "requirements": req_count,
            "skipped": skipped,
        })

    except Exception as e:
        _load_status.update({
            "running": False,
            "done": True,
            "error": str(e),
        })
