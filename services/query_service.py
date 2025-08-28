"""
Query service for ManualMind.
Handles natural language query processing and OpenAI integration.
"""

import os
import hashlib
import json
from typing import List, Dict, Any
import openai
import redis
from dotenv import load_dotenv
from .document_processor import DocumentProcessor

load_dotenv()


class QueryService:
    """Handles query processing and natural language response generation."""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.document_processor = DocumentProcessor()
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True
        )
        # Cache TTL in seconds (24 hours for robust caching)
        self.query_cache_ttl = int(os.getenv("QUERY_CACHE_TTL", 86400))
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent cache keys."""
        # Convert to lowercase, strip whitespace, and normalize spacing
        normalized = ' '.join(query.lower().strip().split())
        return normalized
    
    def _get_query_cache_key(self, query: str, top_k: int = 5) -> str:
        """Generate a hashed cache key for the query."""
        normalized_query = self._normalize_query(query)
        # Include top_k in the key since it affects results
        cache_input = f"{normalized_query}:top_k_{top_k}"
        # Hash to create a reasonable length key
        query_hash = hashlib.md5(cache_input.encode('utf-8')).hexdigest()
        return f"query_cache:{query_hash}"
    
    def generate_response(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """Generate a natural language response using OpenAI based on query and context."""
        
        # Prepare context from relevant chunks
        context_text = "\n\n".join([
            f"From {chunk['file_name']}:\n{chunk['chunk_text']}"
            for chunk in context_chunks
        ])
        
        # Create system prompt based on the README requirements
        system_prompt = """You are ManualMind, an AI assistant that helps users understand and use electronic musical instruments, especially synthesizers. Use device manuals and documentation to answer questions. Provide clear, direct, conversational answers with steps when useful. Reference relevant sections and add helpful context. If the manuals lack the answer, state this clearly."""

        # Create user prompt with context
        user_prompt = f"""Answer the following question using only the manual excerpts provided.

        Question: "{query}"

        Manual excerpts:
        {context_text}

        Give a clear, accurate answer. Include steps if useful. If the manuals don’t fully answer, state what’s missing."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"I apologize, but I encountered an error while processing your question: {str(e)}. Please try again or rephrase your question."
    
    def process_query(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Process a user query and return a structured response."""
        
        # Check Redis cache first
        cache_key = self._get_query_cache_key(query, top_k)
        try:
            cached_response = self.redis_client.get(cache_key)
            if cached_response:
                # Return cached response, bypassing OpenAI call completely
                return json.loads(cached_response)
        except Exception as e:
            # Log cache error but continue with normal processing
            print(f"Cache lookup error: {e}")
        
        # Find relevant document chunks
        similar_chunks = self.document_processor.find_similar_chunks(query, top_k)
        
        if not similar_chunks:
            result = {
                "query": query,
                "response": "I don't have any relevant information in my knowledge base to answer your question. Please make sure the documents are processed and available.",
                "sources": [],
                "confidence": "low",
                "total_sources": 0
            }
            # Cache the no-results response too (shorter TTL)
            try:
                self.redis_client.setex(cache_key, 3600, json.dumps(result))  # 1 hour for no-results
            except Exception as e:
                print(f"Cache store error: {e}")
            return result
        
        # Generate natural language response
        response = self.generate_response(query, similar_chunks)
        
        # Prepare source information
        sources = []
        for chunk in similar_chunks:
            sources.append({
                "file_name": chunk["file_name"],
                "similarity_score": round(chunk["similarity"], 3),
                "preview": chunk["chunk_text"][:200] + "..." if len(chunk["chunk_text"]) > 200 else chunk["chunk_text"]
            })
        
        # Determine confidence based on similarity scores
        max_similarity = max(chunk["similarity"] for chunk in similar_chunks)
        if max_similarity > 0.8:
            confidence = "high"
        elif max_similarity > 0.6:
            confidence = "medium"
        else:
            confidence = "low"
        
        result = {
            "query": query,
            "response": response,
            "sources": sources,
            "confidence": confidence,
            "total_sources": len(similar_chunks)
        }
        
        # Store the result in Redis cache
        try:
            self.redis_client.setex(cache_key, self.query_cache_ttl, json.dumps(result))
        except Exception as e:
            print(f"Cache store error: {e}")
        
        return result