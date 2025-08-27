#!/bin/bash

# ManualMind Deployment Script
# This script helps deploy ManualMind using Docker Compose

set -e

echo "🤖 ManualMind Deployment Script"
echo "================================="

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please create a .env file with your configuration."
    echo "   You can use the provided .env file as a template."
    exit 1
fi

# Check if OpenAI API key is set
if ! grep -q "OPENAI_API_KEY=" .env || grep -q "OPENAI_API_KEY=$" .env; then
    echo "❌ OpenAI API key not found in .env file."
    echo "   Please add your OpenAI API key to the .env file:"
    echo "   OPENAI_API_KEY=your_api_key_here"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Function to start services
start_services() {
    echo "🚀 Starting ManualMind services..."
    
    if [ "$1" == "production" ]; then
        echo "   Using production profile (with Nginx)"
        docker-compose --profile production up -d --build
    else
        echo "   Using development profile"
        docker-compose up -d --build
    fi
    
    echo ""
    echo "⏳ Waiting for services to be healthy..."
    
    # Wait for services to be healthy
    timeout=120
    elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
        if docker-compose ps | grep -q "healthy"; then
            echo "✅ Services are healthy!"
            break
        fi
        sleep 5
        elapsed=$((elapsed + 5))
        echo "   Waiting... ($elapsed/${timeout}s)"
    done
    
    if [ $elapsed -ge $timeout ]; then
        echo "❌ Services did not become healthy within ${timeout} seconds"
        echo "   Check the logs with: docker-compose logs"
        exit 1
    fi
}

# Function to process documents
process_documents() {
    echo ""
    echo "📚 Processing documents in media folder..."
    
    # Check if media folder exists and has PDF files
    if [ ! -d "media" ]; then
        echo "❌ Media folder not found. Creating empty media folder."
        mkdir -p media
        echo "   Please add your PDF files to the media/ folder and run this script again."
        return 1
    fi
    
    pdf_count=$(find media -name "*.pdf" | wc -l)
    if [ $pdf_count -eq 0 ]; then
        echo "⚠️  No PDF files found in media folder."
        echo "   Please add your PDF files to the media/ folder."
        return 1
    fi
    
    echo "   Found $pdf_count PDF file(s) in media folder"
    
    # Trigger document processing
    echo "   Triggering document processing via API..."
    
    max_retries=5
    retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -s -X POST http://localhost:8000/process-documents > /dev/null; then
            echo "✅ Document processing started successfully!"
            break
        else
            retry_count=$((retry_count + 1))
            echo "   Retry $retry_count/$max_retries..."
            sleep 3
        fi
    done
    
    if [ $retry_count -ge $max_retries ]; then
        echo "❌ Failed to start document processing after $max_retries attempts"
        echo "   You can manually trigger processing by visiting: http://localhost:8000"
        return 1
    fi
}

# Function to show status
show_status() {
    echo ""
    echo "📊 Service Status:"
    echo "=================="
    docker-compose ps
    
    echo ""
    echo "🌐 Access Points:"
    echo "================"
    echo "   ManualMind Web Interface: http://localhost:8000"
    echo "   API Documentation: http://localhost:8000/docs"
    echo "   Health Check: http://localhost:8000/health"
    echo "   System Status: http://localhost:8000/status"
    
    if docker-compose ps | grep -q "nginx"; then
        echo "   Production URL: http://localhost"
    fi
    
    echo ""
    echo "📋 Useful Commands:"
    echo "=================="
    echo "   View logs: docker-compose logs -f"
    echo "   Stop services: docker-compose down"
    echo "   Restart: docker-compose restart"
    echo "   Update: docker-compose pull && docker-compose up -d --build"
}

# Parse command line arguments
case "${1:-start}" in
    "start")
        start_services "development"
        process_documents || true
        show_status
        ;;
    "production")
        start_services "production"
        process_documents || true
        show_status
        ;;
    "stop")
        echo "🛑 Stopping ManualMind services..."
        docker-compose down
        echo "✅ Services stopped"
        ;;
    "restart")
        echo "🔄 Restarting ManualMind services..."
        docker-compose restart
        echo "✅ Services restarted"
        show_status
        ;;
    "status")
        show_status
        ;;
    "logs")
        echo "📋 Showing logs (Ctrl+C to exit)..."
        docker-compose logs -f
        ;;
    "update")
        echo "📦 Updating ManualMind..."
        docker-compose pull
        docker-compose up -d --build
        echo "✅ Update complete"
        show_status
        ;;
    "clean")
        echo "🧹 Cleaning up ManualMind..."
        docker-compose down -v
        docker system prune -f
        echo "✅ Cleanup complete"
        ;;
    *)
        echo "Usage: $0 {start|production|stop|restart|status|logs|update|clean}"
        echo ""
        echo "Commands:"
        echo "  start      - Start services in development mode"
        echo "  production - Start services in production mode (with Nginx)"
        echo "  stop       - Stop all services"
        echo "  restart    - Restart all services"
        echo "  status     - Show service status and access points"
        echo "  logs       - Show service logs"
        echo "  update     - Update and rebuild services"
        echo "  clean      - Stop services and clean up volumes/images"
        exit 1
        ;;
esac