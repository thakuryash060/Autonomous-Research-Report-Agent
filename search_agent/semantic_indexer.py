"""
Semantic Indexing & Vector Search Engine for ARA
Implements:
1. Removing stop words
2. Stemming (Porter Stemmer)
3. Inverted & TF-IDF indexing
4. Converting texts to dense vectors (Gemini Embeddings + Offline TF-IDF Fallback)
5. Similarity search algorithm (Cosine Similarity)
6. Prompt-specific search (Matching research papers to Planner sub-questions)
"""

import math
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# =====================================================================
# STEP 1: STOP WORDS REMOVAL
# =====================================================================

STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

def remove_stop_words(tokens: List[str]) -> List[str]:
    """Filter out common stop words from a list of tokens."""
    return [t for t in tokens if t not in STOP_WORDS]


# =====================================================================
# STEP 2: STEMMING (PORTER STEMMER)
# =====================================================================

class PorterStemmer:
    """
    Self-contained pure-Python implementation of the Porter Stemming Algorithm.
    Provides standard suffix reduction without requiring external C libraries or NLTK downloads.
    """
    def __init__(self):
        self.b = ""
        self.k = 0
        self.k0 = 0
        self.j = 0

    def _cons(self, i: int) -> bool:
        if self.b[i] in 'aeiou':
            return False
        if self.b[i] == 'y':
            if i == self.k0:
                return True
            else:
                return not self._cons(i - 1)
        return True

    def _m(self) -> int:
        n = 0
        i = self.k0
        while True:
            if i > self.j:
                return n
            if not self._cons(i):
                break
            i += 1
        i += 1
        while True:
            while True:
                if i > self.j:
                    return n
                if self._cons(i):
                    break
                i += 1
            i += 1
            n += 1
            while True:
                if i > self.j:
                    return n
                if not self._cons(i):
                    break
                i += 1
            i += 1

    def _vowelinstem(self) -> bool:
        for i in range(self.k0, self.j + 1):
            if not self._cons(i):
                return True
        return False

    def _doublec(self, i: int) -> bool:
        if i < self.k0 + 1:
            return False
        if self.b[i] != self.b[i - 1]:
            return False
        return self._cons(i)

    def _cvc(self, i: int) -> bool:
        if i < self.k0 + 2 or not self._cons(i) or self._cons(i - 1) or not self._cons(i - 2):
            return False
        ch = self.b[i]
        if ch in 'wxy':
            return False
        return True

    def _setto(self, s: str):
        n = len(s)
        self.b = self.b[:self.j + 1] + s + self.b[self.j + n + 1:]
        self.k = self.j + n

    def _r(self, s: str):
        if self._m() > 0:
            self._setto(s)

    def _step1ab(self):
        if self.b[self.k] == 's':
            if self.b.endswith('sses', self.k0, self.k + 1):
                self.k -= 2
            elif self.b.endswith('ies', self.k0, self.k + 1):
                self._setto('i')
            elif not self.b.endswith('ss', self.k0, self.k + 1):
                self.k -= 1
        if self.b.endswith('eed', self.k0, self.k + 1):
            if self._m() > 0:
                self.k -= 1
        elif self.b.endswith('ed', self.k0, self.k + 1) or self.b.endswith('ing', self.k0, self.k + 1):
            if self.b.endswith('ed', self.k0, self.k + 1):
                self.j = self.k - 2
            else:
                self.j = self.k - 3
            if self._vowelinstem():
                self.k = self.j
                if self.b.endswith('at', self.k0, self.k + 1) or self.b.endswith('bl', self.k0, self.k + 1) or self.b.endswith('iz', self.k0, self.k + 1):
                    self._setto('e')
                elif self._doublec(self.k):
                    self.k -= 1
                    ch = self.b[self.k]
                    if ch in 'lsz':
                        self.k += 1
                elif self._m() == 1 and self._cvc(self.k):
                    self._setto('e')

    def _step1c(self):
        if self.b.endswith('y', self.k0, self.k + 1) and self._vowelinstem():
            self.b = self.b[:self.k] + 'i' + self.b[self.k + 1:]

    def _step2(self):
        pairs = {
            'ational': 'ate', 'tional': 'tion', 'enci': 'ence', 'anci': 'ance',
            'izer': 'ize', 'bli': 'ble', 'alli': 'al', 'entli': 'ent',
            'eli': 'e', 'ousli': 'ous', 'ization': 'ize', 'ation': 'ate',
            'ator': 'ate', 'alism': 'al', 'iveness': 'ive', 'fulness': 'ful',
            'ousness': 'ous', 'aliti': 'al', 'iviti': 'ive', 'biliti': 'ble'
        }
        for suffix, replacement in pairs.items():
            if self.b.endswith(suffix, self.k0, self.k + 1):
                self.j = self.k - len(suffix)
                if self._m() > 0:
                    self._setto(replacement)
                break

    def _step3(self):
        pairs = {
            'icate': 'ic', 'ative': '', 'alize': 'al', 'iciti': 'ic',
            'ical': 'ic', 'ful': '', 'ness': ''
        }
        for suffix, replacement in pairs.items():
            if self.b.endswith(suffix, self.k0, self.k + 1):
                self.j = self.k - len(suffix)
                if self._m() > 0:
                    self._setto(replacement)
                break

    def _step4(self):
        suffixes = [
            'al', 'ance', 'ence', 'er', 'ic', 'able', 'ible', 'ant',
            'ement', 'ment', 'ent', 'ou', 'ism', 'ate', 'iti', 'ous',
            'ive', 'ize'
        ]
        for suffix in suffixes:
            if self.b.endswith(suffix, self.k0, self.k + 1):
                self.j = self.k - len(suffix)
                if self._m() > 1:
                    self.k = self.j
                return
        if self.b.endswith('ion', self.k0, self.k + 1):
            self.j = self.k - 3
            if self._m() > 1 and (self.b[self.j] == 's' or self.b[self.j] == 't'):
                self.k = self.j

    def _step5(self):
        self.j = self.k
        if self.b[self.k] == 'e':
            a = self._m()
            if a > 1 or (a == 1 and not self._cvc(self.k - 1)):
                self.k -= 1
        if self.b[self.k] == 'l' and self._doublec(self.k) and self._m() > 1:
            self.k -= 1

    def stem(self, word: str) -> str:
        word = word.lower().strip()
        if len(word) <= 2:
            return word
        self.b = word
        self.k = len(word) - 1
        self.k0 = 0
        self.j = self.k
        self._step1ab()
        self._step1c()
        self._step2()
        self._step3()
        self._step4()
        self._step5()
        return self.b[:self.k + 1]


_STEMMER = PorterStemmer()

def stem_word(word: str) -> str:
    """Stem a single word using Porter Stemmer."""
    return _STEMMER.stem(word)

def tokenize_and_preprocess(text: str) -> List[str]:
    """
    Combined Step 1 & Step 2:
    1. Lowercase and regex tokenize
    2. Remove stop words
    3. Stem remaining tokens
    """
    if not text:
        return []
    words = re.findall(r"\b[a-zA-Z]{2,}\b", str(text).lower())
    filtered = remove_stop_words(words)
    stemmed = [stem_word(w) for w in filtered]
    return stemmed


# =====================================================================
# STEP 3: INVERTED INDEXING
# =====================================================================

class InvertedIndex:
    """
    Inverted Index for academic papers and research passages.
    Maps stemmed tokens -> {doc_id: term_frequency}.
    Supports fast BM25 / TF-IDF lexical search.
    """
    def __init__(self):
        # term -> {doc_id: count}
        self.index: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # doc_id -> total token length
        self.doc_lengths: Dict[str, int] = {}
        # doc_id -> metadata (title, abstract, url, etc.)
        self.documents: Dict[str, dict] = {}
        self.total_docs: int = 0

    def add_document(self, doc_id: str, title: str, content: str, metadata: Optional[dict] = None):
        """Index a single document with its title and content."""
        full_text = f"{title} {content}"
        tokens = tokenize_and_preprocess(full_text)
        
        self.doc_lengths[doc_id] = len(tokens)
        self.documents[doc_id] = {
            "doc_id": doc_id,
            "title": title,
            "content": content,
            **(metadata or {})
        }
        
        for token in tokens:
            self.index[token][doc_id] += 1
            
        self.total_docs = len(self.documents)

    def search_bm25(self, query: str, top_k: int = 10, k1: float = 1.5, b: float = 0.75) -> List[Tuple[str, float]]:
        """
        Rank indexed documents against query string using the BM25 scoring algorithm.
        Returns list of (doc_id, score) sorted descending.
        """
        query_tokens = tokenize_and_preprocess(query)
        if not query_tokens or self.total_docs == 0:
            return []

        avg_dl = sum(self.doc_lengths.values()) / max(1, self.total_docs)
        scores: Dict[str, float] = defaultdict(float)

        for token in query_tokens:
            if token not in self.index:
                continue
            
            postings = self.index[token]
            df = len(postings)
            # Standard Robertson-Spärck Jones IDF
            idf = math.log((self.total_docs - df + 0.5) / (df + 0.5) + 1.0)
            
            for doc_id, tf in postings.items():
                doc_len = self.doc_lengths.get(doc_id, avg_dl)
                tf_component = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (doc_len / avg_dl)))
                scores[doc_id] += idf * tf_component

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


# =====================================================================
# STEP 4: CONVERTING TO VECTORS (DENSE EMBEDDINGS)
# =====================================================================

EMBEDDING_MODEL = "gemini-embedding-001"

def embed_texts(gemini_client, texts: List[str], model: str = EMBEDDING_MODEL) -> List[List[float]]:
    """
    Generate dense vector embeddings for a list of texts using Google Gemini API.
    Falls back to deterministic sparse TF-IDF vectors if offline or client is None.
    """
    if not texts:
        return []

    # Clean and bound text length (Gemini embedding context window)
    bounded_texts = [str(t)[:2048] if str(t).strip() else "empty text" for t in texts]

    if gemini_client is not None:
        try:
            # Batch embedding call
            res = gemini_client.models.embed_content(
                model=model,
                contents=bounded_texts,
            )
            if hasattr(res, "embeddings") and res.embeddings:
                return [list(e.values) for e in res.embeddings]
        except Exception as exc:
            # If rate limited or model error, proceed to deterministic fallback
            pass

    # Deterministic Sparse Vector Fallback (Term-hash vectors)
    return [_generate_sparse_vector(t) for t in bounded_texts]


def _generate_sparse_vector(text: str, dim: int = 128) -> List[float]:
    """Generate a normalized 128-dimensional frequency hash vector for offline execution."""
    tokens = tokenize_and_preprocess(text)
    vec = [0.0] * dim
    if not tokens:
        return vec
    for t in tokens:
        idx = abs(hash(t)) % dim
        vec[idx] += 1.0
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


# =====================================================================
# STEP 5: SIMILARITY SEARCH ALGORITHM (COSINE SIMILARITY)
# =====================================================================

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two numeric vectors:
    cos(u, v) = (u . v) / (||u|| * ||v||)
    Implemented in pure Python without requiring NumPy.
    """
    if not vec_a or not vec_b:
        return 0.0
    
    length = min(len(vec_a), len(vec_b))
    dot_product = sum(vec_a[i] * vec_b[i] for i in range(length))
    norm_a = math.sqrt(sum(vec_a[i] * vec_a[i] for i in range(length)))
    norm_b = math.sqrt(sum(vec_b[i] * vec_b[i] for i in range(length)))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return max(-1.0, min(1.0, dot_product / (norm_a * norm_b)))


# =====================================================================
# STEP 6: PROMPT-SPECIFIC SEARCH (HYBRID SEARCH FOR RESEARCH PAPERS)
# =====================================================================

def prompt_specific_search(
    gemini_client,
    question_prompt: str,
    candidate_papers: List[dict],
    inverted_index: Optional[InvertedIndex] = None,
    top_k: int = 5,
    semantic_weight: float = 0.65
) -> List[dict]:
    """
    Step 6: Prompt-specific hybrid search.
    Ranks research papers specifically for a Planner research question or prompt by combining:
    1. Dense semantic vector similarity (Gemini embeddings)
    2. Sparse lexical BM25 matching (Stemmed inverted index)
    
    Returns top_k papers with detailed score diagnostics.
    """
    if not candidate_papers or not question_prompt:
        return []

    # 1. Build Inverted Index if not provided
    if inverted_index is None:
        inverted_index = InvertedIndex()
        for p in candidate_papers:
            pid = str(p.get("source_id", ""))
            title = str(p.get("title", ""))
            content = str(p.get("abstract", "") or p.get("content", ""))
            inverted_index.add_document(pid, title, content)

    # 2. Lexical BM25 Scoring
    bm25_matches = dict(inverted_index.search_bm25(question_prompt, top_k=len(candidate_papers)))
    max_bm25 = max(bm25_matches.values()) if bm25_matches and max(bm25_matches.values()) > 0 else 1.0

    # Two-Stage Optimization: If candidate count is large (> 40), pre-filter with BM25 first
    # to save 90% of embedding API calls and eliminate rate limits!
    active_candidates = candidate_papers
    if len(candidate_papers) > 40:
        # Sort by BM25 first to find top 35 candidates
        bm25_sorted_ids = {pid for pid, _ in sorted(bm25_matches.items(), key=lambda x: x[1], reverse=True)[:35]}
        # Also always include papers that were explicitly marked as counter-evidence or have high existing quality
        active_candidates = [
            p for p in candidate_papers
            if str(p.get("source_id", "")) in bm25_sorted_ids or p.get("score", 0) >= 0.8
        ]
        if len(active_candidates) < top_k:
            active_candidates = candidate_papers[:40]

    # 3. Dense Vector Embedding for the Research Question / Prompt
    prompt_vectors = embed_texts(gemini_client, [question_prompt])
    prompt_vec = prompt_vectors[0] if prompt_vectors else []

    # 4. Embed Papers (Batched or cached) for active candidates
    papers_to_embed = []
    embed_indices = []
    for idx, paper in enumerate(active_candidates):
        if "embedding" not in paper or not paper["embedding"]:
            text = f"{paper.get('title', '')} {paper.get('abstract', '') or paper.get('content', '')}"
            papers_to_embed.append(text)
            embed_indices.append(idx)

    if papers_to_embed:
        new_embeddings = embed_texts(gemini_client, papers_to_embed)
        for i, emb in zip(embed_indices, new_embeddings):
            active_candidates[i]["embedding"] = emb

    # 5. Compute Hybrid Similarity Scores
    scored_results = []
    lexical_weight = 1.0 - semantic_weight

    for paper in active_candidates:
        pid = str(paper.get("source_id", ""))
        paper_vec = paper.get("embedding", [])
        
        # Dense Semantic Cosine Similarity
        vec_sim = cosine_similarity(prompt_vec, paper_vec) if prompt_vec and paper_vec else 0.5
        # Normalize to [0, 1]
        dense_norm = max(0.0, min(1.0, (vec_sim + 1.0) / 2.0)) if vec_sim < 0 else vec_sim

        # Normalized BM25 score
        raw_bm25 = bm25_matches.get(pid, 0.0)
        bm25_norm = min(1.0, raw_bm25 / max_bm25) if max_bm25 > 0 else 0.0

        # Hybrid Score
        hybrid_score = round(semantic_weight * dense_norm + lexical_weight * bm25_norm, 4)

        result_entry = dict(paper)
        result_entry["prompt_similarity_score"] = hybrid_score
        result_entry["semantic_cosine_sim"] = round(vec_sim, 4)
        result_entry["lexical_bm25_score"] = round(raw_bm25, 4)
        scored_results.append(result_entry)

    # Sort descending by hybrid similarity score
    scored_results.sort(key=lambda x: x.get("prompt_similarity_score", 0.0), reverse=True)
    return scored_results[:top_k]


# =====================================================================
# STEP 7: PASSAGE CHUNKING & LOCAL DOCUMENT RE-RANKING
# =====================================================================

def chunk_document_into_passages(
    text: str,
    chunk_size_words: int = 350,
    overlap_words: int = 50
) -> List[Dict[str, Any]]:
    """
    Split a long scientific document or extracted PDF into overlapping semantic passages.
    Preserves paragraph and sentence boundaries wherever possible.
    """
    if not text or not text.strip():
        return []

    # Clean multi-newlines and split by paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks = []
    current_words = []
    current_chunk_idx = 1

    for para in paragraphs:
        p_words = para.split()
        if not p_words:
            continue

        if len(current_words) + len(p_words) <= chunk_size_words:
            current_words.extend(p_words)
        else:
            if current_words:
                chunk_str = " ".join(current_words)
                chunks.append({
                    "chunk_id": f"P{current_chunk_idx}",
                    "content": chunk_str,
                    "title": f"Passage {current_chunk_idx}",
                    "word_count": len(current_words)
                })
                current_chunk_idx += 1
                # Sliding window overlap
                overlap = current_words[-overlap_words:] if len(current_words) > overlap_words else []
                current_words = overlap + p_words
            else:
                current_words = p_words

    if current_words:
        chunk_str = " ".join(current_words)
        chunks.append({
            "chunk_id": f"P{current_chunk_idx}",
            "content": chunk_str,
            "title": f"Passage {current_chunk_idx}",
            "word_count": len(current_words)
        })

    return chunks


def extract_relevant_passages(
    gemini_client,
    document_text: str,
    query_prompt: str,
    top_k: int = 5,
    min_chars_to_chunk: int = 3000
) -> Tuple[str, List[dict]]:
    """
    Deep Passage Chunking & Re-ranking Engine:
    1. If the document is small (< min_chars_to_chunk), returns original text directly.
    2. If it is a full-text academic paper (e.g. 15-page arXiv PDF), chunks into passages.
    3. Builds local InvertedIndex and runs prompt-specific hybrid search (BM25 + Cosine Similarity).
    4. Selects top_k highest-signal passages and restores original document reading order.
    5. Returns formatted focused text with passage citations and diagnostic metadata list.
    """
    if not document_text or len(document_text.strip()) < min_chars_to_chunk or not query_prompt:
        return document_text, []

    passages = chunk_document_into_passages(document_text, chunk_size_words=350, overlap_words=50)
    if len(passages) <= 2:
        return document_text, []

    # Map chunks to candidate format
    chunk_candidates = []
    for p in passages:
        chunk_candidates.append({
            "source_id": p["chunk_id"],
            "title": p["title"],
            "content": p["content"],
            "abstract": p["content"][:200]
        })

    # Rank passages specifically against the research question prompt
    ranked_chunks = prompt_specific_search(
        gemini_client=gemini_client,
        question_prompt=query_prompt,
        candidate_papers=chunk_candidates,
        top_k=min(top_k, len(chunk_candidates)),
        semantic_weight=0.65
    )

    if not ranked_chunks:
        return document_text[:25000], []

    # Map back to preserve original chronological order in paper
    selected_ids = {c["source_id"] for c in ranked_chunks}
    ordered_passages = [p for p in passages if p["chunk_id"] in selected_ids]

    formatted_sections = []
    for p in ordered_passages:
        # Find score
        score = next((c.get("prompt_similarity_score", 0.0) for c in ranked_chunks if c["source_id"] == p["chunk_id"]), 0.0)
        formatted_sections.append(
            f"--- [{p['title']} | Relevance Score: {score:.3f}] ---\n{p['content']}"
        )

    focused_content = "\n\n".join(formatted_sections)
    return focused_content, ranked_chunks


def chunk_and_filter_document(
    text: str,
    query: str = "",
    window_words: int = 350,
    overlap_words: int = 50,
    top_k: int = 5,
    min_chars: int = 3000
) -> str:
    """Wrapper for content_retriever to extract top-k focused passages."""
    focused_text, _ = extract_relevant_passages(
        gemini_client=None,
        document_text=text,
        query_prompt=query,
        top_k=top_k,
        min_chars_to_chunk=min_chars
    )
    return focused_text or text


