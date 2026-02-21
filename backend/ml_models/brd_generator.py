from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
from sentence_transformers import SentenceTransformer
import torch
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import json
from datetime import datetime
import os

class BRDGenerator:
    """
    ML model for generating Business Requirements Documents
    Uses transformer models for text generation and summarization
    """
    
    def __init__(self):
        self.summarizer = pipeline(
            "summarization",
            model="facebook/bart-large-cnn"
        )
        
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.generator = pipeline(
            "text2text-generation",
            model="google/flan-t5-base"
        )
    
    def generate_brd(self, project, include_conflicts=True, 
                     include_traceability=True, include_sentiment=True):
        """
        Generate complete BRD document
        """
        requirements = project.requirements.all()
        data_sources = project.data_sources.filter(is_relevant=True)
        
        brd_content = {
            'title': f"Business Requirements Document - {project.name}",
            'executive_summary': self._generate_executive_summary(project, requirements),
            'business_objectives': self._generate_business_objectives(requirements),
            'stakeholder_analysis': self._generate_stakeholder_analysis(requirements, data_sources),
            'functional_requirements': self._generate_functional_requirements(requirements),
            'non_functional_requirements': self._generate_non_functional_requirements(requirements),
            'assumptions': self._generate_assumptions(requirements, data_sources),
            'success_metrics': self._generate_success_metrics(requirements),
            'timeline': self._generate_timeline(requirements, data_sources),
        }
        
        if include_conflicts:
            brd_content['conflict_analysis'] = self._generate_conflict_analysis(project)
        
        if include_traceability:
            brd_content['traceability_matrix'] = self._generate_traceability_matrix(requirements)
        
        if include_sentiment:
            brd_content['sentiment_analysis'] = self._analyze_sentiment(data_sources)
        
        return brd_content
    
    def _generate_executive_summary(self, project, requirements):
        """Generate executive summary"""
        total_reqs = requirements.count()
        functional_reqs = requirements.filter(requirement_type='functional').count()
        
        summary_input = f"""
        Project: {project.name}
        Description: {project.description}
        Total Requirements: {total_reqs}
        Functional Requirements: {functional_reqs}
        
        This document outlines the business requirements for {project.name}.
        """
        
        if len(summary_input) > 100:
            summary = self.summarizer(
                summary_input,
                max_length=150,
                min_length=50,
                do_sample=False
            )[0]['summary_text']
        else:
            summary = summary_input
        
        executive_summary = f"""
EXECUTIVE SUMMARY

{summary}

This Business Requirements Document (BRD) provides a comprehensive overview of the requirements 
gathered from multiple sources including emails, meeting transcripts, and stakeholder communications.

Total Requirements Identified: {total_reqs}
- Functional Requirements: {functional_reqs}
- Non-Functional Requirements: {requirements.filter(requirement_type='non_functional').count()}
- Business Requirements: {requirements.filter(requirement_type='business').count()}

Document Version: 1.0
Date: {datetime.now().strftime('%B %d, %Y')}
        """
        
        return executive_summary.strip()
    
    def _generate_business_objectives(self, requirements):
        """Generate business objectives section"""
        business_reqs = requirements.filter(requirement_type='business')
        
        objectives = "BUSINESS OBJECTIVES\n\n"
        objectives += "The following business objectives have been identified:\n\n"
        
        for idx, req in enumerate(business_reqs, 1):
            objectives += f"{idx}. {req.title}\n"
            objectives += f"   {req.description}\n"
            objectives += f"   Priority: {req.priority.upper()}\n"
            objectives += f"   Source: {req.data_source.source_type}\n\n"
        
        if not business_reqs:
            objectives += "Business objectives will be derived from functional requirements.\n"
        
        return objectives
    
    def _generate_stakeholder_analysis(self, requirements, data_sources):
        """Generate stakeholder analysis"""
        stakeholders = set()
        for req in requirements:
            if req.stakeholder:
                stakeholders.add(req.stakeholder)
        
        analysis = "STAKEHOLDER ANALYSIS\n\n"
        analysis += f"Total Stakeholders Identified: {len(stakeholders)}\n\n"
        
        for stakeholder in stakeholders:
            stakeholder_reqs = requirements.filter(stakeholder=stakeholder)
            analysis += f"Stakeholder: {stakeholder.title()}\n"
            analysis += f"- Related Requirements: {stakeholder_reqs.count()}\n"
            analysis += f"- Primary Concerns: "
            
            concerns = [req.title for req in stakeholder_reqs[:3]]
            analysis += ", ".join(concerns) + "\n\n"
        
        return analysis
    
    def _generate_functional_requirements(self, requirements):
        """Generate functional requirements section"""
        functional_reqs = requirements.filter(requirement_type='functional')
        
        section = "FUNCTIONAL REQUIREMENTS\n\n"
        section += "The system shall provide the following functional capabilities:\n\n"
        
        for priority in ['high', 'medium', 'low']:
            priority_reqs = functional_reqs.filter(priority=priority)
            if priority_reqs.exists():
                section += f"\n{priority.upper()} PRIORITY:\n\n"
                for idx, req in enumerate(priority_reqs, 1):
                    section += f"FR-{priority[0].upper()}{idx}: {req.title}\n"
                    section += f"Description: {req.description}\n"
                    section += f"Stakeholder: {req.stakeholder or 'General'}\n"
                    section += f"Confidence: {req.confidence_score:.2f}\n"
                    section += f"Source: {req.data_source.source_identifier}\n\n"
        
        return section
    
    def _generate_non_functional_requirements(self, requirements):
        """Generate non-functional requirements section"""
        nfr = requirements.filter(requirement_type='non_functional')
        
        section = "NON-FUNCTIONAL REQUIREMENTS\n\n"
        
        categories = {
            'Performance': ['performance', 'speed', 'response', 'time'],
            'Security': ['security', 'authentication', 'authorization', 'encryption'],
            'Usability': ['usability', 'user', 'interface', 'experience'],
            'Reliability': ['reliability', 'availability', 'uptime'],
            'Scalability': ['scalability', 'scale', 'growth']
        }
        
        for category, keywords in categories.items():
            category_reqs = [
                req for req in nfr 
                if any(kw in req.description.lower() for kw in keywords)
            ]
            
            if category_reqs:
                section += f"\n{category}:\n"
                for idx, req in enumerate(category_reqs, 1):
                    section += f"NFR-{category[:3].upper()}{idx}: {req.title}\n"
                    section += f"   {req.description}\n\n"
        
        return section
    
    def _generate_assumptions(self, requirements, data_sources):
        """Generate assumptions section"""
        assumptions = "ASSUMPTIONS AND CONSTRAINTS\n\n"
        assumptions += "The following assumptions have been made:\n\n"
        assumptions += "1. All stakeholders will be available for requirement validation\n"
        assumptions += "2. Required technical infrastructure is available\n"
        assumptions += "3. Budget and resources are allocated as per project plan\n"
        assumptions += f"4. Data gathered from {data_sources.count()} sources is accurate and complete\n"
        assumptions += "5. Requirements may evolve during the project lifecycle\n"
        
        return assumptions
    
    def _generate_success_metrics(self, requirements):
        """Generate success metrics"""
        metrics = "SUCCESS METRICS\n\n"
        metrics += "The following metrics will be used to measure project success:\n\n"
        metrics += "1. Requirements Coverage\n"
        metrics += f"   - Total requirements implemented: {requirements.count()}\n"
        metrics += f"   - High priority requirements: {requirements.filter(priority='high').count()}\n\n"
        metrics += "2. Stakeholder Satisfaction\n"
        metrics += "   - Measured through feedback surveys and acceptance testing\n\n"
        metrics += "3. Quality Metrics\n"
        metrics += "   - Defect density\n"
        metrics += "   - Test coverage\n"
        metrics += "   - Performance benchmarks\n\n"
        
        return metrics
    
    def _generate_timeline(self, requirements, data_sources):
        """Generate timeline section"""
        timeline = "PROJECT TIMELINE\n\n"
        timeline += "Estimated timeline based on requirements complexity:\n\n"
        
        total_reqs = requirements.count()
        high_priority = requirements.filter(priority='high').count()
        
        weeks = max(4, total_reqs // 5)
        
        timeline += f"Phase 1: Requirements Analysis (2 weeks)\n"
        timeline += f"Phase 2: Design (3 weeks)\n"
        timeline += f"Phase 3: Development ({weeks} weeks)\n"
        timeline += f"Phase 4: Testing (2 weeks)\n"
        timeline += f"Phase 5: Deployment (1 week)\n\n"
        timeline += f"Total Estimated Duration: {weeks + 8} weeks\n"
        
        return timeline
    
    def _generate_conflict_analysis(self, project):
        """Generate conflict analysis"""
        conflicts = project.conflicts.all()
        
        analysis = "CONFLICT ANALYSIS\n\n"
        if conflicts.exists():
            analysis += f"Total Conflicts Detected: {conflicts.count()}\n\n"
            for conflict in conflicts:
                analysis += f"Conflict Type: {conflict.conflict_type}\n"
                analysis += f"Description: {conflict.description}\n"
                analysis += f"Severity: {conflict.severity}\n"
                analysis += f"Status: {'Resolved' if conflict.resolved else 'Pending'}\n\n"
        else:
            analysis += "No conflicts detected between requirements.\n"
        
        return analysis
    
    def _generate_traceability_matrix(self, requirements):
        """Generate requirements traceability matrix"""
        matrix = {}
        
        for req in requirements:
            matrix[f"{req.requirement_type.upper()}-{req.id}"] = {
                'title': req.title,
                'source': req.data_source.source_type,
                'source_id': req.data_source.source_identifier,
                'stakeholder': req.stakeholder,
                'priority': req.priority
            }
        
        return matrix
    
    def _analyze_sentiment(self, data_sources):
        """Analyze sentiment from data sources"""
        sentiment_analyzer = pipeline("sentiment-analysis")
        
        sentiments = {
            'positive': 0,
            'negative': 0,
            'neutral': 0
        }
        
        for source in data_sources[:50]: 
            text = source.raw_content[:512]
            try:
                result = sentiment_analyzer(text)[0]
                label = result['label'].lower()
                if 'pos' in label:
                    sentiments['positive'] += 1
                elif 'neg' in label:
                    sentiments['negative'] += 1
                else:
                    sentiments['neutral'] += 1
            except:
                sentiments['neutral'] += 1
        
        return sentiments
    
    def apply_edit(self, current_content, instruction):
        """Apply natural language edit to content"""
        prompt = f"Edit the following text according to this instruction: {instruction}\n\nText: {current_content}\n\nEdited text:"
        
        try:
            result = self.generator(
                prompt,
                max_length=512,
                num_return_sequences=1
            )
            new_content = result[0]['generated_text']
        except:
            new_content = current_content
        
        return new_content
    
    def generate_document_file(self, brd):
        """Generate Word document file"""
        doc = Document()
        
        title = doc.add_heading(brd.title, 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        info = doc.add_paragraph()
        info.add_run(f"Version: {brd.version}\n").bold = True
        info.add_run(f"Status: {brd.status.upper()}\n").bold = True
        info.add_run(f"Date: {brd.created_at.strftime('%B %d, %Y')}\n").bold = True
        
        doc.add_page_break()
        
        sections = [
            ('Executive Summary', brd.executive_summary),
            ('Business Objectives', brd.business_objectives),
            ('Stakeholder Analysis', brd.stakeholder_analysis),
            ('Functional Requirements', brd.functional_requirements),
            ('Non-Functional Requirements', brd.non_functional_requirements),
            ('Assumptions and Constraints', brd.assumptions),
            ('Success Metrics', brd.success_metrics),
            ('Timeline', brd.timeline),
        ]
        
        if brd.conflict_analysis:
            sections.append(('Conflict Analysis', brd.conflict_analysis))
        
        for section_title, content in sections:
            doc.add_heading(section_title, 1)
            doc.add_paragraph(content)
            doc.add_paragraph()  
        
        filename = f"BRD_{brd.project.name.replace(' ', '_')}_v{brd.version}.docx"
        filepath = os.path.join('/home/claude/brd_generator_project/backend/media', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        doc.save(filepath)
        
        return filepath
