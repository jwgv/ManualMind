"""
ManualMind - AI-powered document search and query system for user manuals.
"""

import os
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Optional, Annotated
import redis
import logging
from datetime import datetime
from dotenv import load_dotenv

from services.document_processor import DocumentProcessor
from services.query_service import QueryService

load_dotenv()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="ManualMind",
    description="AI-powered document search and query system for user manuals with natural language processing capabilities",
    version="0.1.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security setup
security = HTTPBearer(auto_error=False)
API_KEY = os.getenv("MANUALMIND_API_KEY")
AUDIT_LOGGING = os.getenv("AUDIT_LOGGING", "true").lower() == "true"

# Configure logging for audit trail
logging.basicConfig(level=logging.INFO)
audit_logger = logging.getLogger("audit")
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
audit_logger.addHandler(handler)


async def verify_api_key(
        request: Request,
        x_api_key: Annotated[str | None, Header()] = None,
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> bool:
    """Verify API key with multi-tier authentication."""
    # Skip API key verification for public endpoints
    if request.url.path in ["/", "/docs", "/openapi.json", "/health", "/status"]:
        return True

    # Check if this is an internal request from nginx/frontend
    x_internal = request.headers.get("x-internal-request")
    x_forwarded_for = request.headers.get("x-forwarded-for", "")

    # Allow requests from nginx proxy or localhost (frontend)
    client_ip = request.client.host if request.client else "unknown"
    internal_sources = [
        "127.0.0.1", "::1", "localhost",
        "172.20.0.", "172.17.0.", "172.18.0.", "172.19.0.",
        "192.168.", "10.0."
    ]

    is_internal_ip = any(client_ip.startswith(ip) for ip in internal_sources)
    is_nginx_proxy = "172.20.0.5" in x_forwarded_for  # Nginx container IP

    # Allow internal requests (from web UI) without API key
    if is_internal_ip or is_nginx_proxy or x_internal:
        if AUDIT_LOGGING:
            audit_logger.info(
                f"Internal access granted - IP: {client_ip}, Path: {request.url.path}, Internal: {x_internal}")
        return True

    # If no API key is configured, allow access (backward compatibility)
    if not API_KEY:
        return True

    # External requests require API key
    if x_api_key and x_api_key == API_KEY:
        if AUDIT_LOGGING:
            audit_logger.info(f"API access granted via header - IP: {client_ip}, Path: {request.url.path}")
        return True

    if credentials and credentials.credentials == API_KEY:
        if AUDIT_LOGGING:
            audit_logger.info(f"API access granted via bearer - IP: {client_ip}, Path: {request.url.path}")
        return True

    # Log unauthorized access attempt
    if AUDIT_LOGGING:
        audit_logger.warning(f"Unauthorized API access attempt - IP: {client_ip}, Path: {request.url.path}")

    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key. Use X-API-Key header or Authorization Bearer token."
    )

# Initialize services
document_processor = DocumentProcessor()
query_service = QueryService()

# Pydantic models
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="The question to ask about the manuals")
    max_results: Optional[int] = 5

class ProcessDocumentsResponse(BaseModel):
    status: str
    message: str
    processed_files: Optional[list] = None

class QueryResponse(BaseModel):
    query: str
    response: str
    sources: list
    confidence: str
    total_sources: int


@app.get("/")
async def root():
    """Welcome endpoint."""
    return {
        "message": "Welcome to ManualMind - AI-powered manual search system",
        "version": "0.1.0",
        "endpoints": {
            "query": "/query - Ask questions about your manuals",
            "process": "/process-documents - Process PDF files in media folder",
            "status": "/status - Check system status",
            "docs": "/docs - API documentation"
        }
    }


@app.get("/status")
async def get_status():
    """Get system status and available documents."""
    try:
        # Check Redis connection
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0))
        )
        redis_status = "connected" if redis_client.ping() else "disconnected"
        
        # Get processed files
        processed_files = redis_client.get("processed_files")
        processed_files = eval(processed_files) if processed_files else []
        
        return {
            "status": "healthy",
            "redis_status": redis_status,
            "processed_documents": len(processed_files),
            "available_files": processed_files,
            "media_folder": "media"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "redis_status": "disconnected"
        }


@app.post("/process-documents")
async def process_documents(
    background_tasks: BackgroundTasks,
    authenticated: bool = Depends(verify_api_key)
):
    """Process all PDF files in the media folder."""
    def process_in_background():
        try:
            result = document_processor.process_media_folder()
            return result
        except Exception as e:
            print(f"Background processing error: {e}")
    
    background_tasks.add_task(process_in_background)
    
    return {
        "status": "started",
        "message": "Document processing started in background. Check /status for progress."
    }


@app.post("/query", response_model=QueryResponse)
@limiter.limit("10/minute")
async def query_documents(
    request: Request, 
    query_request: QueryRequest,
    authenticated: bool = Depends(verify_api_key)
):
    """Query the processed documents with natural language."""
    try:
        if not query_request.question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        # Process the query
        result = query_service.process_query(
            query_request.question,
            top_k=query_request.max_results
        )
        
        return QueryResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "ManualMind"}


# Mount static files for frontend (if we add a frontend)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
