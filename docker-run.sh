#!/bin/bash
# Neo AI — Docker Helper Script
# =============================
# Usage: ./docker-run.sh [build|up|down|logs|shell|clean]

set -e

COMMAND=${1:-up}
IMAGE_NAME="neo-ai"
CONTAINER_NAME="neo-ai-backend"

case "$COMMAND" in
  build)
    echo "🔨 Building Neo AI Docker image..."
    docker build -t $IMAGE_NAME .
    echo "✅ Build complete"
    ;;

  up)
    echo "🚀 Starting Neo AI stack..."
    docker-compose up -d
    echo "✅ Neo AI running at http://localhost:8000"
    echo "   API docs: http://localhost:8000/docs"
    echo "   Health:   http://localhost:8000/api/health"
    ;;

  down)
    echo "🛑 Stopping Neo AI stack..."
    docker-compose down
    echo "✅ Stopped"
    ;;

  logs)
    echo "📋 Showing logs..."
    docker-compose logs -f neo-api
    ;;

  shell)
    echo "🐚 Opening shell in Neo container..."
    docker exec -it $CONTAINER_NAME /bin/bash
    ;;

  clean)
    echo "🧹 Cleaning up..."
    docker-compose down -v
    docker rmi $IMAGE_NAME 2>/dev/null || true
    echo "✅ Cleaned"
    ;;

  *)
    echo "Neo AI Docker Helper"
    echo ""
    echo "Usage: ./docker-run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  build   — Build the Docker image"
    echo "  up      — Start the stack (default)"
    echo "  down    — Stop the stack"
    echo "  logs    — View container logs"
    echo "  shell   — Open container shell"
    echo "  clean   — Remove containers and images"
    echo ""
    exit 1
    ;;
esac
