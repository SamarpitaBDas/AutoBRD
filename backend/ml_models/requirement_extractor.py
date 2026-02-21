import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from sentence_transformers import SentenceTransformer
import numpy as np
import re
from sklearn.metrics.pairwise import cosine_similarity

class RequirementExtractor:
    """
    ML model for extracting requirements from text using:
    - BERT for text classification (relevance filtering)
    - Sentence transformers for semantic analysis
    - Rule-based NLP for entity extraction
    """
    
    def __init__(self):
        self.relevance_model_name = "distilbert-base-uncased"
        self.tokenizer = AutoTokenizer.from_pretrained(self.relevance_model_name)
        
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli"
        )
        
        # Requirement keywords
        self.requirement_keywords = [
            'must', 'should', 'shall', 'will', 'need', 'require',
            'feature', 'functionality', 'capability', 'support',
            'allow', 'enable', 'provide', 'implement'
        ]
        
        self.requirement_types = [
            'functional requirement',
            'non-functional requirement',
            'business requirement',
            'technical requirement'
        ]
    
    def filter_noise(self, text):
        """
        Filter out noise and determine relevance using ML
        Returns: (is_relevant, relevance_score)
        """
        text = self._clean_text(text)
        
        if len(text.split()) < 5:
            return False, 0.0
        
        keyword_score = self._calculate_keyword_score(text)
        
        semantic_score = self._calculate_semantic_relevance(text)
        
        relevance_score = 0.6 * keyword_score + 0.4 * semantic_score
        
        is_relevant = relevance_score > 0.4
        
        return is_relevant, relevance_score
    
    def extract_requirements(self, text, data_source):
        """
        Extract structured requirements from text
        Returns: list of requirement dictionaries
        """
        requirements = []
        
        sentences = self._split_into_sentences(text)
        
        for sentence in sentences:
            if self._is_requirement_sentence(sentence):
                req_type = self._classify_requirement_type(sentence)
                
                entities = self._extract_entities(sentence)
                
                confidence = self._calculate_confidence(sentence)
                
                requirement = {
                    'requirement_type': req_type,
                    'title': self._generate_title(sentence),
                    'description': sentence,
                    'priority': self._determine_priority(sentence),
                    'stakeholder': entities.get('stakeholder', ''),
                    'confidence_score': confidence
                }
                
                requirements.append(requirement)
        
        return requirements
    
    def _clean_text(self, text):
        """Clean and normalize text"""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        return text.strip()
    
    def _calculate_keyword_score(self, text):
        """Calculate score based on requirement keywords"""
        text_lower = text.lower()
        keyword_count = sum(1 for keyword in self.requirement_keywords if keyword in text_lower)
        return min(keyword_count / 3.0, 1.0)
    
    def _calculate_semantic_relevance(self, text):
        """Calculate semantic relevance using sentence transformers"""
        reference_sentences = [
            "The system must provide user authentication",
            "Users should be able to generate reports",
            "The application needs to support multiple languages"
        ]
        
        text_embedding = self.sentence_model.encode([text])
        reference_embeddings = self.sentence_model.encode(reference_sentences)
        
        similarities = cosine_similarity(text_embedding, reference_embeddings)
        return float(np.max(similarities))
    
    def _split_into_sentences(self, text):
        """Split text into sentences"""
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]
    
    def _is_requirement_sentence(self, sentence):
        """Check if sentence is a requirement"""
        sentence_lower = sentence.lower()
        return any(keyword in sentence_lower for keyword in self.requirement_keywords)
    
    def _classify_requirement_type(self, sentence):
        """Classify requirement type using zero-shot classification"""
        result = self.classifier(sentence, self.requirement_types)
        
        label = result['labels'][0]
        if 'functional' in label:
            return 'functional'
        elif 'non-functional' in label or 'non_functional' in label:
            return 'non_functional'
        elif 'business' in label:
            return 'business'
        else:
            return 'technical'
    
    def _extract_entities(self, sentence):
        """Extract entities like stakeholders"""
        entities = {}
        
        stakeholder_patterns = [
            r'(?:user|customer|client|stakeholder|manager|admin|developer)s?',
            r'(?:team|department|organization)'
        ]
        
        for pattern in stakeholder_patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                entities['stakeholder'] = match.group(0)
                break
        
        return entities
    
    def _calculate_confidence(self, sentence):
        """Calculate confidence score for extracted requirement"""
        score = 0.5  
        
        if any(word in sentence.lower() for word in ['must', 'shall', 'will']):
            score += 0.2
        
        if re.search(r'\d+', sentence):  
            score += 0.1
        
        if len(sentence.split()) > 15:
            score += 0.1
        
        return min(score, 1.0)
    
    def _generate_title(self, sentence):
        """Generate a concise title from sentence"""
        title = sentence[:50]
        if ',' in title:
            title = title.split(',')[0]
        return title.strip() + ('...' if len(sentence) > 50 else '')
    
    def _determine_priority(self, sentence):
        """Determine requirement priority"""
        sentence_lower = sentence.lower()
        
        if any(word in sentence_lower for word in ['critical', 'must', 'essential', 'vital']):
            return 'high'
        elif any(word in sentence_lower for word in ['should', 'important', 'recommended']):
            return 'medium'
        else:
            return 'low'
