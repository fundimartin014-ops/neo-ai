#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# NEO AI — One-Click Server Setup for TRAININGBOT2
# Run: chmod +x setup.sh && ./setup.sh
# ═══════════════════════════════════════════════════════════════

set -e  # Exit on any error

NEO_DIR="/home/ubuntu/TRAININGBOT2"
REPO_URL="https://github.com/yourusername/TRAININGBOT2.git"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           NEO AI — Server Setup Script                       ║"
echo "║           For: TRAININGBOT2                                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# ─── 1. System Update ───
echo "[1/8] Updating system..."
sudo apt-get update && sudo apt-get upgrade -y

# ─── 2. Install Dependencies ───
echo "[2/8] Installing dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    nginx \
    certbot \
    python3-certbot-nginx \
    docker.io \
    docker-compose \
    npm \
    htop \
    ufw

# ─── 3. Install Node.js 20 (for PM2) ───
echo "[3/8] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# ─── 4. Install PM2 ───
echo "[4/8] Installing PM2..."
sudo npm install -g pm2

# ─── 5. Setup Docker ───
echo "[5/8] Setting up Docker..."
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# ─── 6. Clone TRAININGBOT2 ───
echo "[6/8] Cloning TRAININGBOT2..."
if [ -d "$NEO_DIR" ]; then
    echo "  TRAININGBOT2 already exists. Pulling latest..."
    cd "$NEO_DIR" && git pull
else
    git clone "$REPO_URL" "$NEO_DIR"
fi

cd "$NEO_DIR"

# ─── 7. Setup Python Environment ───
echo "[7/8] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ─── 8. Setup Firewall ───
echo "[8/8] Configuring firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 8000
sudo ufw --force enable

# ─── 9. Setup Ollama (Optional) ───
echo "[Bonus] Setting up Ollama..."
sudo docker run -d \
    --name ollama \
    -v ollama:/root/.ollama \
    -p 11434:11434 \
    ollama/ollama:latest || true

# Pull fallback model
sleep 5
sudo docker exec ollama ollama pull qwen2.5:1.5b || true

# ─── 10. Start Neo with PM2 ───
echo "[Bonus] Starting Neo AI with PM2..."
pm2 start ecosystem.config.js
pm2 startup
pm2 save

# ─── Done ───
SERVER_IP=$(curl -s ifconfig.me)
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              ✅ NEO AI SETUP COMPLETE!                       ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  API:       http://${SERVER_IP}:8000                         ║"
echo "║  Health:    http://${SERVER_IP}:8000/api/health              ║"
echo "║  PM2:       pm2 status | pm2 logs neo-ai-api               ║"
echo "║  Ollama:    http://${SERVER_IP}:11434                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Copy your .env file to $NEO_DIR"
echo "  2. Set up SSL: sudo certbot --nginx -d your-domain.com"
echo "  3. Update API keys in .env"
echo "  4. Restart: pm2 restart neo-ai-api"
