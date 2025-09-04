# ManualMind MCP Server Setup Guide

This guide explains how to set up and configure the Model Context Protocol (MCP) server for ManualMind, enabling Claude Desktop and other MCP-compatible clients to query your document database.

## Overview

The MCP server provides a secure interface for AI agents to:
- Search user manuals using natural language queries
- Check system status and available documents
- Trigger document processing operations

## Prerequisites

- Docker and Docker Compose installed
- ManualMind system running via docker-compose
- Claude Desktop (for testing)

## Quick Start

1. **Start the ManualMind stack**:
   ```bash
   docker-compose up -d
   ```

2. **Verify all services are running**:
   ```bash
   docker-compose ps
   ```

3. **Set your API key** (optional but recommended):
   ```bash
   echo "MANUALMIND_API_KEY=your_secure_api_key_here" >> .env
   ```

4. **Configure Claude Desktop** by adding the configuration from `claude_desktop_config_http_via_stdio.json`

On Macs, the location of the configuration file is:
`~/Library/Application Support/Claude Desktop/config/claude_desktop_config.json`

5. **Update the file path** in the configuration to match your system

6. **Restart Claude Desktop**

## Configuration Options

### HTTP-via-stdio Configuration (Recommended for HTTP mode)

Use this configuration to run the MCP server in HTTP mode via stdio bridge:

```json
{
  "mcpServers": {
    "manualmind-http": {
      "command": "bash",
      "args": [
        "/path/to/ManualMind/scripts/mcp_client_stdio.sh"
      ],
      "env": {
        "MCP_SERVER_HOST": "localhost",
        "MCP_SERVER_PORT": "8001",
        "MANUALMIND_API_KEY": "--PUT-KEY-HERE--"
      }
    }
  }
}
```

### Docker-based Configuration

Use this configuration when running ManualMind via Docker Compose:

```json
{
  "mcpServers": {
    "manualmind": {
      "command": "docker",
      "args": [
        "compose",
        "-f",
        "/absolute/path/to/ManualMind/docker-compose.yml",
        "exec",
        "-T",
        "mcp-server",
        "python",
        "main.py"
      ],
      "env": {
        "MANUALMIND_API_URL": "http://manualmind:8000",
        "MANUALMIND_API_KEY": "your_secure_api_key_here",
        "API_TIMEOUT": "30",
        "RATE_LIMIT_PER_MINUTE": "10",
        "LOG_LEVEL": "INFO",
        "AUDIT_LOGGING": "true"
      }
    }
  }
}
```

**Note**: Update the path in the `args` array to match your actual ManualMind installation directory.

### Direct Python Configuration (Alternative)

If you have the MCP server installed locally:

```json
{
  "mcpServers": {
    "manualmind": {
      "command": "python",
      "args": ["/absolute/path/to/ManualMind/mcp_server/main.py"],
      "env": {
        "MANUALMIND_API_URL": "http://localhost:8000",
        "MANUALMIND_API_KEY": "your_secure_api_key_here",
        "API_TIMEOUT": "30",
        "RATE_LIMIT_PER_MINUTE": "10",
        "LOG_LEVEL": "INFO",
        "AUDIT_LOGGING": "true"
      }
    }
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MANUALMIND_API_URL` | URL of the ManualMind API | `http://manualmind:8000` |
| `MANUALMIND_API_KEY` | API key for authentication | None (optional) |
| `API_TIMEOUT` | Request timeout in seconds | `30` |
| `RATE_LIMIT_PER_MINUTE` | Max requests per minute | `10` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `AUDIT_LOGGING` | Enable audit logging | `true` |

## Available Tools

### query_manuals
Search for information in user manuals using natural language.

**Parameters:**
- `question` (string): The question to ask about the manuals (1-500 characters)
- `max_results` (integer, optional): Maximum number of results to return (1-20, default: 5)

### get_system_status
Get the status of the ManualMind system including available documents and health.

**Parameters:** None

### process_documents
Trigger processing of documents in the ManualMind media folder.

**Parameters:** None

## Security Features

- **API Key Authentication**: Secure access using X-API-Key header or Authorization Bearer token
- **Rate Limiting**: Prevents abuse with configurable limits
- **Audit Logging**: Comprehensive logging for compliance and monitoring
- **Network Isolation**: Docker networking provides secure inter-service communication
- **Non-root Execution**: MCP server runs as non-root user for enhanced security

## Usage Examples

Once configured in Claude Desktop, you can use natural language to query your manuals:

### Example Queries
- "Search the JUNO-X manual for information about MIDI configuration"
- "What are the available synthesis modes in the SYSTEM-8?"
- "How do I connect external audio sources?"
- "Show me the system status and available documents"
- "Process any new documents in the media folder"

### Expected Response Format
```
Query: How do I configure MIDI on the JUNO-X?

Answer: [AI-generated response based on manual content]

Confidence: high
Total sources found: 3

Sources:
1. File: JUNO-X_Reference_eng01_W.pdf
   Score: 0.95
   Content: MIDI settings can be configured in the System menu...

2. File: JUNO-X_Reference_eng01_W.pdf
   Score: 0.87
   Content: To set up MIDI channels, navigate to...
```

## Troubleshooting

### Common Issues

1. **Connection refused**: Ensure ManualMind services are running
2. **Authentication errors**: Check your API key configuration
3. **Path not found**: Verify absolute paths in the configuration
4. **Rate limiting**: Reduce request frequency or increase limits

### Checking Logs

```bash
# View MCP server logs
docker-compose logs mcp-server

# View ManualMind API logs
docker-compose logs manualmind

# View all services
docker-compose logs
```

### Health Checks

```bash
# Check service status
docker-compose ps

# Test API directly
curl http://localhost:8000/health

# Test with API key
curl -H "X-API-Key: your_api_key_here" http://localhost:8000/status
```

## Advanced Configuration

### Custom Rate Limiting
Modify the environment variables in docker-compose.yml:

```yaml
environment:
  - RATE_LIMIT_PER_MINUTE=20  # Increase limit
```

### Custom Logging
Configure structured JSON logging:

```yaml
environment:
  - LOG_FORMAT=json
  - LOG_LEVEL=DEBUG
```

### Production Deployment
For production use, consider:

1. Using secrets management for API keys
2. Setting up log aggregation
3. Configuring monitoring and alerting
4. Using HTTPS with proper certificates
5. Implementing backup and recovery procedures

## Support

For issues and questions:
1. Check the logs for error messages
2. Verify configuration against this guide
3. Ensure all services are healthy
4. Test API endpoints directly

The MCP server provides comprehensive error messages and audit trails to help diagnose issues.