# 🤖 ManualMind

> AI-powered document search and query system for user manuals with natural language processing capabilities

ManualMind is an intelligent document assistant that helps users find answers to questions about their synthesizer manuals using natural language queries. Built with FastAPI, OpenAI integration, and vector search capabilities.

## ✨ Features

- **Natural Language Queries**: Ask questions in plain English about your manuals
- **Intelligent Document Processing**: Automatically processes PDF manuals with chunking and vectorization
- **AI-Powered Responses**: Uses OpenAI GPT to generate contextual, helpful answers
- **Vector Search**: Fast similarity search using sentence transformers
- **Web Interface**: Clean, modern web UI for easy interaction
- **Redis Caching**: High-performance caching for processed documents and queries
- **Rate Limiting**: API rate limiting to prevent abuse
- **Docker Deployment**: Complete containerization with Docker Compose
- **Health Monitoring**: Built-in health checks and status monitoring
- **MCP Server Integration**: Model Context Protocol server for Claude Desktop and other MCP-compatible clients

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key
- PDF manuals in the `media/` folder

### 1. Clone and Setup

```bash
git clone <repository-url>
cd ManualMind
```

### 2. Configure Environment

Update the `.env` file with your OpenAI API key:

```bash
# ManualMind Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Application Settings
MAX_CHUNK_SIZE=1000
CHUNK_OVERLAP=100
RATE_LIMIT_PER_MINUTE=10
```

### 3. Add Your Manuals

Place your PDF manuals in the `media/` folder:

```bash
media/
├── JUNO-X_Editor_eng01_W.pdf
├── JUNO-X_MIDI_imple_eng01_W.pdf
├── JUNO-X_Sound_Install_eng02_W.pdf
├── JUNO-X_VocalDesigner_eng02_W.pdf
└── ... (add your manuals here)
```

### 4. Deploy

Use the automated deployment script:

```bash
# Start in development mode
./scripts/deploy.sh start

# Or start in production mode (with Nginx)
./scripts/deploy.sh production
```

### 5. Access the Application

- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 🤖 MCP Server Integration

ManualMind includes a Model Context Protocol (MCP) server that enables Claude Desktop and other MCP-compatible clients to query your document database using natural language.

### MCP Setup

For detailed MCP server configuration, see the [MCP Setup Guide](MCP_SETUP.md).

#### Quick MCP Configuration

1. **Ensure ManualMind is running**:
   ```bash
   ./scripts/deploy.sh start
   ```

2. **Add to Claude Desktop config** (`claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "manualmind-http": {
         "command": "bash",
         "args": ["/path/to/ManualMind/scripts/mcp_client_stdio.sh"],
         "env": {
           "MCP_SERVER_HOST": "localhost",
           "MCP_SERVER_PORT": "8001",
           "MANUALMIND_API_KEY": "your_api_key_here"
         }
       }
     }
   }
   ```

3. **Update the path** to match your ManualMind installation

4. **Restart Claude Desktop**

#### Available MCP Tools

- **query_manuals**: Search manuals using natural language
- **get_system_status**: Check system health and available documents  
- **process_documents**: Trigger document processing

For complete setup instructions, configuration options, and troubleshooting, see the [MCP Setup Guide](MCP_SETUP.md).

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Claude        │    │   MCP Server    │    │   FastAPI       │    ┌─────────────────┐
│   Desktop       │◄──►│   (Port 8001)   │◄──►│   Backend       │◄──►│   OpenAI API    │
│   (MCP Client)  │    │                 │    │   (Port 8000)   │    │   GPT-3.5       │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Redis Cache   │◄──►│   Document      │    │   PDF Files     │
│   (HTML/JS)     │◄──►│   (Embeddings)  │    │   Processor     │◄──►│   (media/)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow

1. **Document Processing**: PDFs are extracted, chunked, and vectorized
2. **Query Processing**: User questions are converted to embeddings (via web UI or MCP)
3. **Vector Search**: Similar document chunks are retrieved
4. **AI Response**: OpenAI generates contextual responses
5. **Caching**: Results cached in Redis for performance
6. **MCP Integration**: Claude Desktop and other MCP clients can query the system through the MCP server

## 🛠️ Development

### Local Development Setup

```bash
# Install dependencies with UV
pip install uv
uv pip install -e .

# Start Redis locally
docker run -d -p 6379:6379 redis:7-alpine

# Run the application
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Welcome and API overview |
| `/query` | POST | Submit natural language queries |
| `/process-documents` | POST | Process PDF files in media folder |
| `/status` | GET | System health and document status |
| `/health` | GET | Simple health check |
| `/docs` | GET | Interactive API documentation |

### Query API Example

```bash
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "How do I use the vocoder on my Roland Juno X?",
       "max_results": 5
     }'
```

## 🐳 Docker Commands

### Using the Deployment Script

```bash
# Available commands
./scripts/deploy.sh {start|production|stop|restart|status|logs|update|clean}

# Examples
./scripts/deploy.sh start      # Start development environment
./scripts/deploy.sh production # Start with Nginx reverse proxy
./scripts/deploy.sh logs       # View application logs
./scripts/deploy.sh status     # Check service status
./scripts/deploy.sh stop       # Stop all services
```

### Manual Docker Commands

```bash
# Build and start services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Clean up everything
docker-compose down -v
docker system prune -f
```

## 🌐 Production Deployment

### Digital Ocean Droplet

1. Create a droplet with Docker pre-installed
2. Clone the repository
3. Configure environment variables
4. Run the production deployment:

```bash
./scripts/deploy.sh production
```

### AWS/Other Cloud Providers

The Docker Compose setup works on any cloud provider that supports Docker:

- Update the `.env` file with production settings
- Ensure proper firewall rules (ports 80, 443, 8000)
- Use production profile for Nginx reverse proxy
- Consider using managed Redis service for production

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `REDIS_HOST` | Redis server hostname | localhost |
| `REDIS_PORT` | Redis server port | 6379 |
| `MAX_CHUNK_SIZE` | Document chunk size | 1000 |
| `CHUNK_OVERLAP` | Chunk overlap size | 100 |
| `RATE_LIMIT_PER_MINUTE` | API rate limit | 10 |

### Adding New Documents

1. Place PDF files in the `media/` folder
2. Restart the application or call `/process-documents` endpoint
3. Documents are automatically processed and cached

## 📊 Monitoring

### Health Checks

- Application health: `/health`
- System status: `/status`
- Docker health checks built into containers

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f manualmind
docker-compose logs -f redis
```

## ❓ Example Usage

**User Question**: "How do I use the vocoder on my Roland Juno X?"

**System Response**: To use the vocoder on your Roland Juno X, follow these steps:

1. Connect a microphone to the rear panel MIC IN jack on the Juno X. Use a dynamic microphone or an electret condenser microphone (plug-in power system) as condenser microphones are not supported.
2. Adjust the volume of the microphone input using the rear panel MIC IN GAIN knob. Start by setting the knob to the center position and make detailed adjustments after selecting the sound.
3. Select part 1 on the Juno X and press the MODEL BANK button to illuminate it.
4. Press the MODEL BANK button and then press button 6. By default, the "VOCODER" is assigned to the model bank of button 6. You can change the assigned model bank if needed.
5. Use the [- VALUE +] knob to select a vocoder sound from the two types available.
6. While playing the keyboard, vocalize into the microphone. The vocoder effect will be applied to your voice.

If you want to input audio playback from your computer instead of using the microphone input for the vocoder:
1. Connect the Juno X to your computer via USB.
2. Choose "OUT MIC" as the audio output device of your computer. This way, the audio playback from your computer can be used for the vocoder performance.

For further details on setting up the USB driver and audio settings, refer to the sections in the manual related to USB audio settings and driver installation.

Confidence: MEDIUM

Sources (5)

JUNO-X_Reference_eng01_W.pdf

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with the deployment script
5. Submit a pull request

## 🆘 Troubleshooting

### Common Issues

**Q: Services won't start**
- Check Docker and Docker Compose installation
- Verify `.env` file has OpenAI API key
- Run `./scripts/deploy.sh logs` to see error details

**Q: No documents processed**
- Ensure PDF files are in `media/` folder
- Call `/process-documents` endpoint manually
- Check Redis connection in `/status`

**Q: Slow responses**
- Increase Redis memory allocation
- Check OpenAI API rate limits
- Consider using local embedding models

For more issues, check the logs with `./scripts/deploy.sh logs` or open an issue on GitHub.



