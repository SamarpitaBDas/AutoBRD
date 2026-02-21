from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.http import FileResponse
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
import os

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    
    @action(detail=True, methods=['post'])
    def sync_data_sources(self, request, pk=None):
        """Sync data from connected sources"""
        project = self.get_object()
        
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
                days=request.data.get('days', 30)
            )
            for message in messages:
                DataSource.objects.create(
                    project=project,
                    source_type='slack',
                    source_identifier=message['ts'],
                    raw_content=message['text'],
                    metadata=message['metadata']
                )
        
        return Response({'status': 'Data sources synced'})

class DataSourceViewSet(viewsets.ModelViewSet):
    queryset = DataSource.objects.all()
    serializer_class = DataSourceSerializer
    
    @action(detail=False, methods=['post'])
    def upload_document(self, request):
        """Upload and process document"""
        project_id = request.data.get('project_id')
        file = request.FILES.get('file')
        
        if not file or not project_id:
            return Response(
                {'error': 'Missing file or project_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Read file content
        content = file.read().decode('utf-8', errors='ignore')
        
        data_source = DataSource.objects.create(
            project_id=project_id,
            source_type='document',
            source_identifier=file.name,
            raw_content=content,
            metadata={'filename': file.name, 'size': file.size}
        )
        
        return Response(DataSourceSerializer(data_source).data)
    
    @action(detail=False, methods=['post'])
    def process_sources(self, request):
        """Extract requirements from data sources"""
        project_id = request.data.get('project_id')
        sources = DataSource.objects.filter(project_id=project_id)
        
        extractor = RequirementExtractor()
        
        for source in sources:
            is_relevant, relevance_score = extractor.filter_noise(source.raw_content)
            source.is_relevant = is_relevant
            source.relevance_score = relevance_score
            source.save()
            
            if is_relevant:
                requirements = extractor.extract_requirements(source.raw_content, source)
                for req in requirements:
                    ExtractedRequirement.objects.create(
                        project_id=project_id,
                        data_source=source,
                        **req
                    )
        
        return Response({'status': 'Requirements extracted'})

class ExtractedRequirementViewSet(viewsets.ModelViewSet):
    queryset = ExtractedRequirement.objects.all()
    serializer_class = ExtractedRequirementSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

class BRDDocumentViewSet(viewsets.ModelViewSet):
    queryset = BRDDocument.objects.all()
    serializer_class = BRDDocumentSerializer
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate BRD document"""
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
            include_sentiment=data['include_sentiment']
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
            traceability_matrix=brd_content.get('traceability_matrix', {}),
            sentiment_analysis=brd_content.get('sentiment_analysis', {})
        )
        
        file_path = generator.generate_document_file(brd)
        brd.file_path = file_path
        brd.save()
        
        return Response(BRDDocumentSerializer(brd).data)
    
    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        """Edit BRD document with natural language"""
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
            new_content=new_content
        )
        
        return Response(BRDDocumentSerializer(brd).data)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download BRD document file"""
        brd = self.get_object()
        
        if not brd.file_path or not os.path.exists(brd.file_path):
            generator = BRDGenerator()
            file_path = generator.generate_document_file(brd)
            brd.file_path = file_path
            brd.save()
        
        return FileResponse(
            open(brd.file_path, 'rb'),
            as_attachment=True,
            filename=f"BRD_{brd.project.name}_v{brd.version}.docx"
        )

class ConflictDetectionViewSet(viewsets.ModelViewSet):
    queryset = ConflictDetection.objects.all()
    serializer_class = ConflictDetectionSerializer
    
    @action(detail=False, methods=['post'])
    def detect_conflicts(self, request):
        """Detect conflicts in requirements"""
        project_id = request.data.get('project_id')
        requirements = ExtractedRequirement.objects.filter(project_id=project_id)
        
        detector = ConflictDetector()
        conflicts = detector.detect_conflicts(list(requirements))
        
        for conflict in conflicts:
            ConflictDetection.objects.create(
                project_id=project_id,
                **conflict
            )
        
        return Response({'status': f'{len(conflicts)} conflicts detected'})

@api_view(['GET'])
def health_check(request):
    """API health check"""
    return Response({'status': 'healthy'})
