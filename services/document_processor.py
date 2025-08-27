"""
Document processing service for ManualMind.
Handles PDF loading, text chunking, and embedding generation.
"""

import os
import hashlib
from typing import List, Dict, Any
from pathlib import Path
import PyPDF2
import openai
from sentence_transformers import SentenceTransformer
import numpy as np
import redis
import json
from dotenv import load_dotenv

load_dotenv()


class DocumentProcessor:
    """Handles document processing, chunking, and embedding generation."""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True
        )
        self.max_chunk_size = int(os.getenv("MAX_CHUNK_SIZE", 1000))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", 100))
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF file."""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error extracting text from {pdf_path}: {e}")
            return ""
        return text
    
    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks for better context preservation."""
        if len(text) <= self.max_chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.max_chunk_size
            
            # Try to break at sentence or paragraph boundaries
            if end < len(text):
                # Look for sentence endings within the last 200 characters
                last_period = text.rfind('.', start, end)
                last_newline = text.rfind('\n\n', start, end)
                
                if last_period > start + self.max_chunk_size * 0.8:
                    end = last_period + 1
                elif last_newline > start + self.max_chunk_size * 0.8:
                    end = last_newline + 2
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
            
        return chunks
    
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for text chunks using sentence transformer."""
        return self.embedding_model.encode(texts)
    
    def get_file_hash(self, file_path: str) -> str:
        """Generate hash for file to check if it's already processed."""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def process_document(self, file_path: str) -> Dict[str, Any]:
        """Process a single document: extract text, chunk, and generate embeddings."""
        file_hash = self.get_file_hash(file_path)
        cache_key = f"doc:{file_hash}"
        
        # Check if already processed
        cached = self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Extract text
        text = self.extract_text_from_pdf(file_path)
        if not text.strip():
            return {"error": f"No text extracted from {file_path}"}
        
        # Chunk text
        chunks = self.chunk_text(text)
        
        # Generate embeddings
        embeddings = self.generate_embeddings(chunks)
        
        # Prepare document data
        doc_data = {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "file_hash": file_hash,
            "chunks": chunks,
            "embeddings": embeddings.tolist(),  # Convert to list for JSON serialization
            "total_chunks": len(chunks)
        }
        
        # Cache the processed document
        self.redis_client.setex(cache_key, 86400, json.dumps(doc_data))  # Cache for 24 hours
        
        return doc_data
    
    def process_media_folder(self, media_path: str = "media") -> Dict[str, Any]:
        """Process all PDF files in the media folder."""
        if not os.path.exists(media_path):
            return {"error": f"Media folder {media_path} not found"}
        
        results = {}
        pdf_files = list(Path(media_path).glob("*.pdf"))
        
        for pdf_file in pdf_files:
            print(f"Processing {pdf_file.name}...")
            result = self.process_document(str(pdf_file))
            results[pdf_file.name] = result
        
        # Store processed files list in Redis
        self.redis_client.setex("processed_files", 86400, json.dumps(list(results.keys())))
        
        return results
    
    def find_similar_chunks(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Find the most similar text chunks to a query using vector similarity."""
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query])
        
        # Get all processed files
        processed_files = self.redis_client.get("processed_files")
        if not processed_files:
            return []
        
        processed_files = json.loads(processed_files)
        all_similarities = []
        
        for file_name in processed_files:
            # Find the document by file name
            for key in self.redis_client.scan_iter(match="doc:*"):
                doc_data = json.loads(self.redis_client.get(key))
                if doc_data.get("file_name") == file_name:
                    embeddings = np.array(doc_data["embeddings"])
                    chunks = doc_data["chunks"]
                    
                    # Calculate cosine similarity
                    similarities = np.dot(query_embedding, embeddings.T).flatten()
                    
                    for i, similarity in enumerate(similarities):
                        all_similarities.append({
                            "file_name": file_name,
                            "chunk_index": i,
                            "chunk_text": chunks[i],
                            "similarity": float(similarity),
                            "file_path": doc_data.get("file_path", "")
                        })
                    break
        
        # Sort by similarity and return top_k
        all_similarities.sort(key=lambda x: x["similarity"], reverse=True)
        return all_similarities[:top_k]