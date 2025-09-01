"""
MCP Server for ManualMind API
Model Context Protocol server that provides access to ManualMind document query capabilities.
Supports both stdio MCP protocol and HTTP REST API for flexible access.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    TextContent,
    Tool,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HTTP API Models
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="The question to ask about the manuals")
    max_results: Optional[int] = Field(default=5, ge=1, le=20, description="Maximum number of results to return")

class ToolCallRequest(BaseModel):
    name: str = Field(..., description="Tool name to call")
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Tool arguments")

class ToolResponse(BaseModel):
    success: bool
    content: str
    error: Optional[str] = None

class ManualMindMCPServer:
    """MCP Server for ManualMind API integration."""
    
    def __init__(self):
        self.server = Server("manualmind-mcp")
        self.base_url = os.getenv("MANUALMIND_API_URL", "http://manualmind:8000")
        self.api_timeout = int(os.getenv("API_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        
        # Security configuration
        self.api_key = os.getenv("MANUALMIND_API_KEY")
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
        
        # Setup request tracking for rate limiting
        self.request_timestamps = []
        
        # Initialize FastAPI app for HTTP access
        self.app = FastAPI(
            title="ManualMind MCP Server HTTP API",
            description="HTTP interface for ManualMind MCP Server",
            version="0.1.0"
        )
        
        self.setup_handlers()
        self.setup_http_routes()
    
    def setup_handlers(self):
        """Setup MCP server handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> ListToolsResult:
            """List available tools."""
            return ListToolsResult(
                tools=[
                    Tool(
                        name="query_manuals",
                        description="Query the ManualMind system to search for information in user manuals using natural language",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "The question to ask about the manuals",
                                    "minLength": 1,
                                    "maxLength": 500
                                },
                                "max_results": {
                                    "type": "integer",
                                    "description": "Maximum number of results to return (default: 5)",
                                    "minimum": 1,
                                    "maximum": 20,
                                    "default": 5
                                }
                            },
                            "required": ["question"]
                        }
                    ),
                    Tool(
                        name="get_system_status",
                        description="Get the status of the ManualMind system including available documents and health",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    ),
                    Tool(
                        name="process_documents",
                        description="Trigger processing of documents in the ManualMind media folder",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    )
                ]
            )
        
        @self.server.call_tool()
        async def call_tool(request: CallToolRequest) -> CallToolResult:
            """Handle tool calls."""
            try:
                # Rate limiting check
                if not self._check_rate_limit():
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Rate limit exceeded. Maximum {self.rate_limit_per_minute} requests per minute allowed."
                        )],
                        isError=True
                    )
                
                if request.name == "query_manuals":
                    return await self._query_manuals(request.arguments or {})
                elif request.name == "get_system_status":
                    return await self._get_system_status()
                elif request.name == "process_documents":
                    return await self._process_documents()
                else:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Unknown tool: {request.name}"
                        )],
                        isError=True
                    )
                    
            except Exception as e:
                logger.error(f"Error calling tool {request.name}: {e}")
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"Error executing tool: {str(e)}"
                    )],
                    isError=True
                )
    
    def _check_rate_limit(self) -> bool:
        """Check if request is within rate limits."""
        import time
        current_time = time.time()
        
        # Remove old timestamps (older than 1 minute)
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if current_time - ts < 60
        ]
        
        # Check if we're under the limit
        if len(self.request_timestamps) >= self.rate_limit_per_minute:
            return False
        
        # Add current timestamp
        self.request_timestamps.append(current_time)
        return True
    
    async def _query_manuals(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Query the ManualMind API."""
        question = arguments.get("question", "").strip()
        max_results = arguments.get("max_results", 5)
        
        if not question:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="Question cannot be empty"
                )],
                isError=True
            )
        
        try:
            async with httpx.AsyncClient(timeout=self.api_timeout) as client:
                headers = {}
                if self.api_key:
                    headers["X-API-Key"] = self.api_key
                
                response = await client.post(
                    urljoin(self.base_url, "/query"),
                    json={
                        "question": question,
                        "max_results": max_results
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Format the response nicely
                    formatted_response = self._format_query_response(result)
                    
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=formatted_response
                        )]
                    )
                else:
                    error_msg = f"API request failed with status {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=error_msg
                        )],
                        isError=True
                    )
                    
        except httpx.TimeoutException:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="Request timed out. The ManualMind API may be unavailable."
                )],
                isError=True
            )
        except Exception as e:
            logger.error(f"Error querying manuals: {e}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Error querying manuals: {str(e)}"
                )],
                isError=True
            )
    
    async def _get_system_status(self) -> CallToolResult:
        """Get system status from ManualMind API."""
        try:
            async with httpx.AsyncClient(timeout=self.api_timeout) as client:
                headers = {}
                if self.api_key:
                    headers["X-API-Key"] = self.api_key
                
                response = await client.get(
                    urljoin(self.base_url, "/status"),
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    formatted_status = self._format_status_response(result)
                    
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=formatted_status
                        )]
                    )
                else:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Failed to get status: {response.status_code} - {response.text}"
                        )],
                        isError=True
                    )
                    
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Error getting system status: {str(e)}"
                )],
                isError=True
            )
    
    async def _process_documents(self) -> CallToolResult:
        """Trigger document processing."""
        try:
            async with httpx.AsyncClient(timeout=self.api_timeout) as client:
                headers = {}
                if self.api_key:
                    headers["X-API-Key"] = self.api_key
                
                response = await client.post(
                    urljoin(self.base_url, "/process-documents"),
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Document processing {result.get('status', 'unknown')}: {result.get('message', 'No message')}"
                        )]
                    )
                else:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Failed to process documents: {response.status_code} - {response.text}"
                        )],
                        isError=True
                    )
                    
        except Exception as e:
            logger.error(f"Error processing documents: {e}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Error processing documents: {str(e)}"
                )],
                isError=True
            )
    
    def _format_query_response(self, result: Dict[str, Any]) -> str:
        """Format query response for better readability."""
        query = result.get("query", "")
        response = result.get("response", "")
        sources = result.get("sources", [])
        confidence = result.get("confidence", "unknown")
        total_sources = result.get("total_sources", 0)
        
        formatted = f"Query: {query}\n\n"
        formatted += f"Answer: {response}\n\n"
        formatted += f"Confidence: {confidence}\n"
        formatted += f"Total sources found: {total_sources}\n\n"
        
        if sources:
            formatted += "Sources:\n"
            for i, source in enumerate(sources, 1):
                if isinstance(source, dict):
                    file_name = source.get("file", "Unknown file")
                    content = source.get("content", "No content")
                    score = source.get("score", "N/A")
                    formatted += f"{i}. File: {file_name}\n"
                    formatted += f"   Score: {score}\n"
                    formatted += f"   Content: {content[:200]}{'...' if len(content) > 200 else ''}\n\n"
                else:
                    formatted += f"{i}. {str(source)[:200]}{'...' if len(str(source)) > 200 else ''}\n\n"
        
        return formatted
    
    def _format_status_response(self, result: Dict[str, Any]) -> str:
        """Format status response for better readability."""
        status = result.get("status", "unknown")
        redis_status = result.get("redis_status", "unknown")
        processed_docs = result.get("processed_documents", 0)
        available_files = result.get("available_files", [])
        
        formatted = f"System Status: {status}\n"
        formatted += f"Redis Status: {redis_status}\n"
        formatted += f"Processed Documents: {processed_docs}\n\n"
        
        if available_files:
            formatted += "Available Files:\n"
            for file in available_files:
                formatted += f"  - {file}\n"
        else:
            formatted += "No documents have been processed yet.\n"
        
        return formatted

    def setup_http_routes(self):
        """Setup HTTP routes for REST API access."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint with server information."""
            return {
                "service": "ManualMind MCP Server",
                "version": "0.1.0",
                "endpoints": {
                    "tools": "/tools - List available tools",
                    "call": "/call - Call a tool",
                    "query": "/query - Direct query endpoint",
                    "status": "/status - Get system status",
                    "process": "/process - Process documents"
                }
            }
        
        @self.app.get("/tools")
        async def list_tools():
            """List available tools via HTTP."""
            try:
                # Use the existing MCP tool list logic
                tools = [
                    {
                        "name": "query_manuals",
                        "description": "Query the ManualMind system to search for information in user manuals using natural language",
                        "parameters": {
                            "question": "string (required, 1-500 chars)",
                            "max_results": "integer (optional, 1-20, default: 5)"
                        }
                    },
                    {
                        "name": "get_system_status", 
                        "description": "Get the status of the ManualMind system including available documents and health",
                        "parameters": {}
                    },
                    {
                        "name": "process_documents",
                        "description": "Trigger processing of documents in the ManualMind media folder",
                        "parameters": {}
                    }
                ]
                return {"tools": tools}
            except Exception as e:
                logger.error(f"Error listing tools via HTTP: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/call", response_model=ToolResponse)
        async def call_tool(request: ToolCallRequest):
            """Call a tool via HTTP."""
            try:
                # Create MCP CallToolRequest
                mcp_request = CallToolRequest(
                    method="tools/call",
                    params={
                        "name": request.name,
                        "arguments": request.arguments
                    }
                )
                
                # Use existing MCP call logic
                if request.name == "query_manuals":
                    result = await self._query_manuals(request.arguments)
                elif request.name == "get_system_status":
                    result = await self._get_system_status()
                elif request.name == "process_documents":
                    result = await self._process_documents()
                else:
                    return ToolResponse(
                        success=False,
                        content="",
                        error=f"Unknown tool: {request.name}"
                    )
                
                # Extract content from MCP result
                content = ""
                if result.content:
                    content = "\n".join([
                        item.text if hasattr(item, 'text') else str(item)
                        for item in result.content
                    ])
                
                return ToolResponse(
                    success=not result.isError,
                    content=content,
                    error=content if result.isError else None
                )
                
            except Exception as e:
                logger.error(f"Error calling tool {request.name} via HTTP: {e}")
                return ToolResponse(
                    success=False,
                    content="",
                    error=str(e)
                )
        
        @self.app.post("/query", response_model=ToolResponse)
        async def query_manuals(request: QueryRequest):
            """Direct query endpoint for convenience."""
            try:
                arguments = {
                    "question": request.question,
                    "max_results": request.max_results
                }
                result = await self._query_manuals(arguments)
                
                content = ""
                if result.content:
                    content = "\n".join([
                        item.text if hasattr(item, 'text') else str(item)
                        for item in result.content
                    ])
                
                return ToolResponse(
                    success=not result.isError,
                    content=content,
                    error=content if result.isError else None
                )
                
            except Exception as e:
                logger.error(f"Error in direct query via HTTP: {e}")
                return ToolResponse(
                    success=False,
                    content="",
                    error=str(e)
                )
        
        @self.app.get("/status", response_model=ToolResponse)
        async def get_status():
            """Get system status via HTTP."""
            try:
                result = await self._get_system_status()
                
                content = ""
                if result.content:
                    content = "\n".join([
                        item.text if hasattr(item, 'text') else str(item)
                        for item in result.content
                    ])
                
                return ToolResponse(
                    success=not result.isError,
                    content=content,
                    error=content if result.isError else None
                )
                
            except Exception as e:
                logger.error(f"Error getting status via HTTP: {e}")
                return ToolResponse(
                    success=False,
                    content="",
                    error=str(e)
                )
        
        @self.app.post("/process", response_model=ToolResponse)
        async def process_documents():
            """Process documents via HTTP."""
            try:
                result = await self._process_documents()
                
                content = ""
                if result.content:
                    content = "\n".join([
                        item.text if hasattr(item, 'text') else str(item)
                        for item in result.content
                    ])
                
                return ToolResponse(
                    success=not result.isError,
                    content=content,
                    error=content if result.isError else None
                )
                
            except Exception as e:
                logger.error(f"Error processing documents via HTTP: {e}")
                return ToolResponse(
                    success=False,
                    content="",
                    error=str(e)
                )


async def run_http_server(server: ManualMindMCPServer):
    """Run the HTTP API server."""
    import uvicorn
    config = uvicorn.Config(
        app=server.app,
        host="0.0.0.0",
        port=int(os.getenv("MCP_HTTP_PORT", "8001")),
        log_level="info"
    )
    http_server = uvicorn.Server(config)
    await http_server.serve()

async def run_stdio_server(server: ManualMindMCPServer):
    """Run the MCP stdio server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.server.run(
            read_stream=read_stream,
            write_stream=write_stream,
            initialization_options={}
        )

async def main():
    """Main entry point for the MCP server."""
    server = ManualMindMCPServer()
    
    # Log startup information
    logger.info("Starting ManualMind MCP Server (Hybrid Mode)")
    logger.info(f"API URL: {server.base_url}")
    logger.info(f"API Timeout: {server.api_timeout}s")
    logger.info(f"Rate Limit: {server.rate_limit_per_minute}/minute")
    logger.info(f"HTTP Port: {os.getenv('MCP_HTTP_PORT', '8001')}")
    
    # Determine run mode
    run_mode = os.getenv("MCP_RUN_MODE", "hybrid").lower()
    
    if run_mode == "http":
        # Run only HTTP server
        logger.info("Running in HTTP-only mode")
        await run_http_server(server)
    elif run_mode == "stdio":
        # Run only stdio server
        logger.info("Running in stdio-only mode")
        await run_stdio_server(server)
    else:
        # Run both servers (hybrid mode)
        logger.info("Running in hybrid mode (both HTTP and stdio)")
        async with asyncio.TaskGroup() as tg:
            tg.create_task(run_http_server(server))
            # For hybrid mode, we need to handle stdio differently
            # In Docker, we'll primarily use HTTP mode
            logger.info("HTTP server started, waiting for connections...")


if __name__ == "__main__":
    asyncio.run(main())