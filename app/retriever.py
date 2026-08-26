# Aster & Row Support Agent - Knowledge Base Retriever

import os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.knowledge import load_knowledge_base

# Lightweight sentence transformer model instance (runs locally on CPU)
_embedding_model_instance = None

def get_embedding_model():
    global _embedding_model_instance
    if _embedding_model_instance is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
            _embedding_model_instance = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"Error loading SentenceTransformer: {e}. Semantic search will be unavailable.")
            _embedding_model_instance = None
    return _embedding_model_instance

class HybridRetriever:
    def __init__(self, kb_dir="knowledge-base"):
        self.chunks = load_knowledge_base(kb_dir)
        self.texts = []
        
        # Prepare text representation for each chunk
        for chunk in self.chunks:
            # We construct a representation that includes metadata to help match search terms
            rep = f"Document Title: {chunk['title']}\nHeading: {chunk['heading']}\nContent: {chunk['text']}"
            self.texts.append(rep)
            
        # Fit TF-IDF Vectorizer for Keyword Search
        self.vectorizer = TfidfVectorizer(stop_words='english')
        if self.texts:
            self.tfidf_matrix = self.vectorizer.fit_transform(self.texts)
        else:
            self.tfidf_matrix = None
            
        # Precompute or Load Semantic Embeddings from Cache
        embeddings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings.npy")
        if os.path.exists(embeddings_path):
            self.embeddings = np.load(embeddings_path)
        else:
            emb_model = get_embedding_model()
            if emb_model and self.texts:
                self.embeddings = emb_model.encode(self.texts, show_progress_bar=False)
                np.save(embeddings_path, self.embeddings)
            else:
                self.embeddings = None

    def retrieve(self, query, top_k=3, confidence_threshold=0.35, semantic_weight=0.7):
        """
        Retrieves top relevant chunks using hybrid search and metadata re-ranking.
        Returns a list of retrieved chunks with their scores.
        """
        if not self.chunks or not self.texts:
            return []

        # 1. Semantic Similarity
        semantic_scores = np.zeros(len(self.chunks))
        emb_model = get_embedding_model()
        if emb_model and self.embeddings is not None:
            query_emb = emb_model.encode([query], show_progress_bar=False)
            # cosine_similarity returns matrix of shape (1, num_chunks)
            semantic_scores = cosine_similarity(query_emb, self.embeddings)[0]

        # 2. Keyword Similarity (TF-IDF)
        keyword_scores = np.zeros(len(self.chunks))
        if self.vectorizer and self.tfidf_matrix is not None:
            query_tfidf = self.vectorizer.transform([query])
            keyword_scores = cosine_similarity(query_tfidf, self.tfidf_matrix)[0]

        results = []
        for idx, chunk in enumerate(self.chunks):
            sem_score = float(semantic_scores[idx])
            key_score = float(keyword_scores[idx])
            
            # Combine scores
            hybrid_score = (semantic_weight * sem_score) + ((1.0 - semantic_weight) * key_score)
            
            # 3. Metadata Re-ranking
            # "Prefer authoritative, active policy documents over superseded or non-policy documents."
            final_score = hybrid_score
            
            status = chunk.get("status", "active").lower()
            authority = chunk.get("policy_authority", "official").lower()
            
            # Avoid penalizing if the user query is explicitly inquiring about these non-authoritative files
            query_lower = query.lower()
            
            # Penalize superseded documents unless query explicitly asks about legacy/superseded/old docs
            if status == "superseded":
                inquires_legacy = any(w in query_lower for w in ["legacy", "superseded", "old", "previous"])
                if not inquires_legacy:
                    final_score -= 0.35
            
            # Penalize draft/non-authoritative scratchpads unless query explicitly asks about draft/migration/notes
            elif status == "draft" or authority == "none":
                inquires_draft = any(w in query_lower for w in ["migration", "draft", "scratchpad", "notes"])
                if not inquires_draft:
                    final_score -= 0.35
                
            # If active and official, give a small boost
            elif status == "active" and authority == "official":
                final_score += 0.05
                
            # Clamp score to [0, 1]
            final_score = max(0.0, min(1.0, final_score))
            
            results.append({
                "chunk": chunk,
                "semantic_score": sem_score,
                "keyword_score": key_score,
                "hybrid_score": hybrid_score,
                "final_score": final_score
            })
            
        # Sort by final score in descending order
        results.sort(key=lambda x: x["final_score"], reverse=True)
        
        # 4. Confidence Threshold Check
        # If the top score is below threshold, we return empty to signify insufficient info.
        if not results or results[0]["final_score"] < confidence_threshold:
            # We still return the results but flag them as low confidence, or return empty list
            # Let's return the results but we will let the agent check if top score is < threshold.
            pass
            
        return results[:top_k]

# Create a singleton instance for global use
_retriever_instance = None

def get_retriever():
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever()
    return _retriever_instance

if __name__ == "__main__":
    retriever = get_retriever()
    q = "What is the return window for a normal backpack?"
    hits = retriever.retrieve(q, top_k=3)
    print(f"\nQuery: {q}")
    for i, hit in enumerate(hits):
        c = hit["chunk"]
        print(f"Rank {i+1}: Score={hit['final_score']:.3f} File={c['source']} Heading='{c['heading']}'")
