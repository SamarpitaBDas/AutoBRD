from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re

class ConflictDetector:
    """
    ML model for detecting conflicts between requirements
    Uses semantic similarity and rule-based analysis
    """
    
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.contradiction_words = [
            'not', 'never', 'without', 'except', 'unless',
            'cannot', 'should not', 'must not'
        ]
        
        self.conflict_types = {
            'functional': 'Functional conflict - requirements specify different behaviors',
            'constraint': 'Constraint conflict - requirements have incompatible constraints',
            'priority': 'Priority conflict - requirements have conflicting priorities',
            'resource': 'Resource conflict - requirements compete for same resources',
            'temporal': 'Temporal conflict - requirements have timing conflicts'
        }
    
    def detect_conflicts(self, requirements):
        """
        Detect conflicts between requirements
        Returns list of conflict dictionaries
        """
        conflicts = []
        
        req_list = list(requirements)
        
        for i in range(len(req_list)):
            for j in range(i + 1, len(req_list)):
                req1 = req_list[i]
                req2 = req_list[j]
                
                conflict = self._check_conflict(req1, req2)
                
                if conflict:
                    conflicts.append(conflict)
        
        return conflicts
    
    def _check_conflict(self, req1, req2):
        """Check if two requirements conflict"""
        similarity = self._calculate_similarity(req1.description, req2.description)
        
        if similarity > 0.7:
            has_contradiction = self._check_contradiction(req1.description, req2.description)
            
            if has_contradiction:
                return {
                    'requirement1': req1,
                    'requirement2': req2,
                    'conflict_type': 'functional',
                    'description': f"Requirements appear contradictory despite semantic similarity. "
                                 f"Req1: {req1.title[:100]}. Req2: {req2.title[:100]}.",
                    'severity': 'high'
                }
        
        priority_conflict = self._check_priority_conflict(req1, req2, similarity)
        if priority_conflict:
            return priority_conflict
        
        resource_conflict = self._check_resource_conflict(req1, req2)
        if resource_conflict:
            return resource_conflict
        
        constraint_conflict = self._check_constraint_conflict(req1, req2)
        if constraint_conflict:
            return constraint_conflict
        
        return None
    
    def _calculate_similarity(self, text1, text2):
        """Calculate semantic similarity between two texts"""
        embeddings = self.model.encode([text1, text2])
        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        return float(similarity)
    
    def _check_contradiction(self, text1, text2):
        """Check if texts contain contradictory statements"""
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        text1_negation = any(word in text1_lower for word in self.contradiction_words)
        text2_negation = any(word in text2_lower for word in self.contradiction_words)
        
        return text1_negation != text2_negation
    
    def _check_priority_conflict(self, req1, req2, similarity):
        """Check for priority conflicts"""
        if similarity > 0.6 and req1.priority != req2.priority:
            priority_order = {'high': 3, 'medium': 2, 'low': 1}
            
            if abs(priority_order[req1.priority] - priority_order[req2.priority]) >= 2:
                return {
                    'requirement1': req1,
                    'requirement2': req2,
                    'conflict_type': 'priority',
                    'description': f"Similar requirements have conflicting priorities. "
                                 f"{req1.title} is {req1.priority}, {req2.title} is {req2.priority}.",
                    'severity': 'medium'
                }
        
        return None
    
    def _check_resource_conflict(self, req1, req2):
        """Check for resource conflicts"""
        exclusive_keywords = ['exclusive', 'only', 'sole', 'single']
        
        req1_exclusive = any(kw in req1.description.lower() for kw in exclusive_keywords)
        req2_exclusive = any(kw in req2.description.lower() for kw in exclusive_keywords)
        
        if req1_exclusive and req2_exclusive:
            req1_words = set(req1.description.lower().split())
            req2_words = set(req2.description.lower().split())
            overlap = len(req1_words.intersection(req2_words))
            
            if overlap > 3: 
                return {
                    'requirement1': req1,
                    'requirement2': req2,
                    'conflict_type': 'resource',
                    'description': f"Both requirements may require exclusive access to same resource.",
                    'severity': 'high'
                }
        
        return None
    
    def _check_constraint_conflict(self, req1, req2):
        """Check for constraint conflicts"""
        req1_numbers = self._extract_numbers(req1.description)
        req2_numbers = self._extract_numbers(req2.description)
        
        constraint_keywords = ['maximum', 'minimum', 'limit', 'at least', 'no more than']
        
        req1_has_constraint = any(kw in req1.description.lower() for kw in constraint_keywords)
        req2_has_constraint = any(kw in req2.description.lower() for kw in constraint_keywords)
        
        if req1_has_constraint and req2_has_constraint and req1_numbers and req2_numbers:
            if any(abs(n1 - n2) > max(n1, n2) * 0.5 for n1 in req1_numbers for n2 in req2_numbers):
                return {
                    'requirement1': req1,
                    'requirement2': req2,
                    'conflict_type': 'constraint',
                    'description': f"Requirements specify potentially conflicting numeric constraints.",
                    'severity': 'medium'
                }
        
        return None
    
    def _extract_numbers(self, text):
        """Extract numeric values from text"""
        numbers = re.findall(r'\d+\.?\d*', text)
        return [float(n) for n in numbers]
    
    def calculate_conflict_severity(self, conflict):
        """Calculate severity score for a conflict"""
        severity_scores = {
            'high': 1.0,
            'medium': 0.6,
            'low': 0.3
        }
        
        return severity_scores.get(conflict.get('severity', 'medium'), 0.5)
