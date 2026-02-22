"""
requirement_extractor.py
─────────────────────────
ML pipeline for extracting structured requirements from raw text.

New capabilities added for Enron / Slack dataset support:
  • filter_for_product()    — keeps only sentences about *your* target product
                              when a message discusses multiple products.
  • get_product_sentences() — returns the product-focused portion of a message.
  • filter_noise()          — original relevance gate (unchanged).
  • extract_requirements()  — unchanged public API.
"""

import re
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class RequirementExtractor:
    """
    ML model for extracting requirements from text using:
    - BERT / DistilBERT tokenizer
    - Sentence transformers for semantic analysis & product scoping
    - Zero-shot classification for requirement typing
    - Rule-based NLP for entity extraction
    """

    def __init__(self):
        self.relevance_model_name = "distilbert-base-uncased"
        self.tokenizer = AutoTokenizer.from_pretrained(self.relevance_model_name)
        self.sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
        )

        self.requirement_keywords = [
            "must", "should", "shall", "will", "need", "require",
            "feature", "functionality", "capability", "support",
            "allow", "enable", "provide", "implement",
        ]
        self.requirement_types = [
            "functional requirement",
            "non-functional requirement",
            "business requirement",
            "technical requirement",
        ]

    # ── PUBLIC API ────────────────────────────────────────────────────────────

    def filter_noise(self, text: str):
        """
        General-purpose relevance filter (original behaviour, unchanged).
        Returns: (is_relevant: bool, relevance_score: float)
        """
        text = self._clean_text(text)
        if len(text.split()) < 5:
            return False, 0.0
        keyword_score = self._calculate_keyword_score(text)
        semantic_score = self._calculate_semantic_relevance(text)
        relevance_score = 0.6 * keyword_score + 0.4 * semantic_score
        return relevance_score > 0.4, relevance_score

    def filter_for_product(self, text: str, product_topic: str):
        """
        ── NEW ──
        Handles messages that discuss multiple products / topics (common in
        Slack channels and email threads).

        How it works
        ------------
        1. Splits the message into sentences.
        2. Embeds each sentence and the product_topic using sentence-transformers.
        3. Keeps only sentences whose cosine similarity to the topic >= threshold.
        4. Runs keyword scoring on the kept sentences to confirm requirement language.

        Returns: (is_relevant: bool, relevance_score: float)
        """
        sentences = self._split_into_sentences(text)
        if not sentences:
            return False, 0.0

        product_sentences, avg_sim = self._select_product_sentences(sentences, product_topic)
        if not product_sentences:
            return False, 0.0

        focused_text = " ".join(product_sentences)
        keyword_score = self._calculate_keyword_score(focused_text)
        combined = 0.5 * avg_sim + 0.5 * keyword_score
        is_relevant = combined > 0.3 and avg_sim > 0.25

        return is_relevant, float(combined)

    def get_product_sentences(self, text: str, product_topic: str, threshold: float = 0.30) -> str:
        """
        ── NEW ──
        Returns only the sentences from `text` that are about `product_topic`.

        Use this BEFORE extract_requirements() when a message covers multiple
        products so that requirements from unrelated products don't leak in.

        Example
        -------
            focused = extractor.get_product_sentences(slack_msg, "energy trading")
            requirements = extractor.extract_requirements(focused, data_source)
        """
        sentences = self._split_into_sentences(text)
        if not sentences:
            return text
        product_sentences, _ = self._select_product_sentences(sentences, product_topic, threshold)
        return " ".join(product_sentences) if product_sentences else text

    def extract_requirements(self, text: str, data_source):
        """
        Extract structured requirements from text.
        Returns: list of requirement dicts ready for DB insertion.
        """
        requirements = []
        sentences = self._split_into_sentences(text)

        for sentence in sentences:
            if self._is_requirement_sentence(sentence):
                req_type = self._classify_requirement_type(sentence)
                entities = self._extract_entities(sentence)
                confidence = self._calculate_confidence(sentence)
                requirements.append({
                    "requirement_type": req_type,
                    "title": self._generate_title(sentence),
                    "description": sentence,
                    "priority": self._determine_priority(sentence),
                    "stakeholder": entities.get("stakeholder", ""),
                    "confidence_score": confidence,
                })

        return requirements

    # ── PRIVATE — product scoping ─────────────────────────────────────────────

    def _select_product_sentences(self, sentences, product_topic, threshold=0.30):
        """
        Score each sentence against product_topic and return those >= threshold,
        plus the average similarity of kept sentences.
        """
        if not sentences:
            return [], 0.0

        topic_emb = self.sentence_model.encode([product_topic])
        sent_embs = self.sentence_model.encode(sentences)
        sims = cosine_similarity(topic_emb, sent_embs)[0]

        kept = [s for s, sim in zip(sentences, sims) if sim >= threshold]
        kept_sims = sims[sims >= threshold]
        avg_sim = float(np.mean(kept_sims)) if len(kept_sims) > 0 else 0.0

        return kept, avg_sim

    # ── PRIVATE — original helpers ────────────────────────────────────────────

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\s.,!?-]", "", text)
        return text.strip()

    def _calculate_keyword_score(self, text: str) -> float:
        lower = text.lower()
        count = sum(1 for kw in self.requirement_keywords if kw in lower)
        return min(count / 3.0, 1.0)

    def _calculate_semantic_relevance(self, text: str) -> float:
        reference_sentences = [
            "The system must provide user authentication",
            "Users should be able to generate reports",
            "The application needs to support multiple languages",
        ]
        text_emb = self.sentence_model.encode([text])
        ref_emb = self.sentence_model.encode(reference_sentences)
        sims = cosine_similarity(text_emb, ref_emb)
        return float(np.max(sims))

    def _split_into_sentences(self, text: str):
        sentences = re.split(r"[.!?\n]+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def _is_requirement_sentence(self, sentence: str) -> bool:
        return any(kw in sentence.lower() for kw in self.requirement_keywords)

    def _classify_requirement_type(self, sentence: str) -> str:
        result = self.classifier(sentence, self.requirement_types)
        label = result["labels"][0]
        if "functional" in label and "non" not in label:
            return "functional"
        elif "non-functional" in label or "non_functional" in label:
            return "non_functional"
        elif "business" in label:
            return "business"
        return "technical"

    def _extract_entities(self, sentence: str) -> dict:
        entities = {}
        patterns = [
            r"(?:user|customer|client|stakeholder|manager|admin|developer)s?",
            r"(?:team|department|organization)",
        ]
        for pattern in patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                entities["stakeholder"] = match.group(0)
                break
        return entities

    def _calculate_confidence(self, sentence: str) -> float:
        score = 0.5
        if any(w in sentence.lower() for w in ["must", "shall", "will"]):
            score += 0.2
        if re.search(r"\d+", sentence):
            score += 0.1
        if len(sentence.split()) > 15:
            score += 0.1
        return min(score, 1.0)

    def _generate_title(self, sentence: str) -> str:
        title = sentence[:50]
        if "," in title:
            title = title.split(",")[0]
        return title.strip() + ("..." if len(sentence) > 50 else "")

    def _determine_priority(self, sentence: str) -> str:
        lower = sentence.lower()
        if any(w in lower for w in ["critical", "must", "essential", "vital"]):
            return "high"
        elif any(w in lower for w in ["should", "important", "recommended"]):
            return "medium"
        return "low"
