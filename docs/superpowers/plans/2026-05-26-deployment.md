# Deployment Plan — Canine Wisdom Automation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the pipeline to a cloud server so it runs automatically every day without needing a local machine, with a simple way to monitor runs and update the code.

**Architecture:** A single low-cost VPS (Hetzner CX22 or DigitalOcean Droplet) runs the pipeline on a daily cron. Docker packages all dependencies (Python, ffmpeg, GPU optional). GitHub is the deployment mechanism — push code, SSH pull on server. Credentials are stored as environment variables on the server, never in git. A simple log viewer (via SSH or a tiny web page) shows recent run status.

**Tech Stack:** Docker + docker-compose, Ubuntu 22.04 VPS, GitHub, cron, ffmpeg, Python 3.12.

---

## Deployment Options Compared

| Option | Cost/month | GPU | Setup effort | Best for |
|---|---|---|---|---|
| **Hetzner CX22** (recommended) | ~$5 | No (CPU encode) | Low | Daily cron, cheap |
| DigitalOcean Basic Droplet | ~$6 | No | Low | Same as Hetzner |
| RunPod / Vast.ai (GPU) | ~$15–30 | Yes (faster encode) | Medium | If speed matters |
| GitHub Actions | Free (2000 min/mo) | No | Medium | Zero infra |
| Local machine + cron | $0 | Yes | Already done | Dev/testing |

**Recommendation: Hetzner CX22** — €3.79/month, 2 vCPU, 4GB RAM, 40GB SSD, Ubuntu 22.04. CPU encoding with libx264 takes ~60s instead of ~5s with GPU, which is fine for a daily job. Total pipeline run: ~3–4 minutes.

---

## File Map

| File | Change |
|---|---|
| `Dockerfile` | **New** — packages Python + ffmpeg + dependencies |
| `docker-compose.yml` | **New** — mounts credentials, footage, data volumes |
| `.dockerignore` | **New** — excludes venv, outputs, archive, footage from image |
| `deploy/setup.sh` | **New** — one-shot server setup script |
| `deploy/update.sh` | **New** — git pull + docker rebuild + restart |
| `deploy/cron.sh` | **New** — wrapper called by cron, logs output |
| `.github/workflows/deploy.yml` | **New** (optional) — auto-deploy on push to main |

---

## Task 1: Create Dockerfile and docker-compose.yml

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

# Install ffmpeg and system deps
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command — run the orchestrator
CMD ["python", "-m", "harness.orchestrator"]
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
version: "3.9"

services:
  pipeline:
    build: .
    env_file: .env
    volumes:
      # Persist footage library, state, credentials, archive across runs
      - ./dog_footage:/app/dog_footage
      - ./harness/data:/app/harness/data
      - ./assets:/app/assets
      - ./archive:/app/archive
      - ./client_secrets.json:/app/client_secrets.json:ro
      - ./token.json:/app/token.json
      - ./youtube_settings.json:/app/youtube_settings.json:ro
    restart: "no"
```

- [ ] **Step 3: Create `.dockerignore`**

```
venv/
__pycache__/
*.pyc
outputs/
run_logs/
.git/
*.log
```

- [ ] **Step 4: Build and test locally**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
docker build -t canine-wisdom .
```
Expected: build succeeds, image created.

- [ ] **Step 5: Test run locally (dry-run import check)**

```bash
docker run --rm canine-wisdom python -c "from harness.orchestrator import run_pipeline; print('Import OK')"
```
Expected: `Import OK`

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: add Dockerfile and docker-compose for deployment"
```

---

## Task 2: Create deploy scripts

**Files:**
- Create: `deploy/setup.sh` — one-shot server setup
- Create: `deploy/update.sh` — pull latest code and restart
- Create: `deploy/cron.sh` — daily cron wrapper with logging

- [ ] **Step 1: Create `deploy/` directory and `setup.sh`**

```bash
mkdir -p deploy
```

Create `deploy/setup.sh`:

```bash
#!/bin/bash
# One-shot server setup. Run once after provisioning a fresh Ubuntu 22.04 VPS.
# Usage: bash deploy/setup.sh

set -e

echo "=== Installing Docker ==="
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

echo "=== Installing Docker Compose ==="
apt-get install -y docker-compose-plugin

echo "=== Cloning repo ==="
cd /opt
git clone https://github.com/YOUR_GITHUB_USERNAME/canine-wisdom-automation.git canine-wisdom
cd canine-wisdom

echo "=== Creating required directories ==="
mkdir -p dog_footage harness/data assets/music archive outputs run_logs

echo ""
echo "=== NEXT STEPS ==="
echo "1. Copy your .env file to /opt/canine-wisdom/.env"
echo "2. Copy client_secrets.json and token.json to /opt/canine-wisdom/"
echo "3. Copy youtube_settings.json to /opt/canine-wisdom/"
echo "4. Copy your dog_footage/ clips to /opt/canine-wisdom/dog_footage/"
echo "5. Copy assets/music/ MP3s to /opt/canine-wisdom/assets/music/"
echo "6. Run: bash deploy/update.sh"
echo "7. Set up cron: crontab -e"
echo "   Add: 0 9 * * * /opt/canine-wisdom/deploy/cron.sh"
```

- [ ] **Step 2: Create `deploy/update.sh`**

```bash
#!/bin/bash
# Pull latest code from git and rebuild Docker image.
# Usage: bash deploy/update.sh

set -e
cd /opt/canine-wisdom

echo "=== Pulling latest code ==="
git pull origin master

echo "=== Rebuilding Docker image ==="
docker compose build

echo "=== Done. Next run will use updated image. ==="
```

- [ ] **Step 3: Create `deploy/cron.sh`**

```bash
#!/bin/bash
# Daily cron wrapper. Runs the pipeline and logs output.
# Crontab entry: 0 9 * * * /opt/canine-wisdom/deploy/cron.sh

set -e
cd /opt/canine-wisdom

LOG_DIR="/opt/canine-wisdom/run_logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cron_$(date +%Y-%m-%d_%H-%M-%S).log"

echo "=== Starting pipeline: $(date) ===" | tee "$LOG_FILE"
docker compose run --rm pipeline 2>&1 | tee -a "$LOG_FILE"
echo "=== Pipeline finished: $(date) ===" | tee -a "$LOG_FILE"

# Keep only last 30 log files
ls -t "$LOG_DIR"/cron_*.log | tail -n +31 | xargs -r rm
```

- [ ] **Step 4: Make scripts executable**

```bash
chmod +x deploy/setup.sh deploy/update.sh deploy/cron.sh
```

- [ ] **Step 5: Commit**

```bash
git add deploy/
git commit -m "feat: add deploy scripts for VPS setup, update, and daily cron"
```

---

## Task 3: Add GitHub Actions auto-deploy (optional but recommended)

**Files:**
- Create: `.github/workflows/deploy.yml`

This workflow SSHes into the server and runs `update.sh` whenever you push to master.

- [ ] **Step 1: Create `.github/workflows/deploy.yml`**

```yaml
name: Deploy to VPS

on:
  push:
    branches: [master]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            bash /opt/canine-wisdom/deploy/update.sh
```

- [ ] **Step 2: Add GitHub secrets**

In your GitHub repo → Settings → Secrets → Actions, add:
- `VPS_HOST` — your server IP address
- `VPS_USER` — `root` or your SSH username
- `VPS_SSH_KEY` — your private SSH key (contents of `~/.ssh/id_rsa`)

- [ ] **Step 3: Commit**

```bash
git add .github/
git commit -m "feat: add GitHub Actions auto-deploy on push to master"
```

---

## Task 4: Server provisioning step-by-step

This is a manual task — no code to write.

- [ ] **Step 1: Create Hetzner account and provision server**

Go to https://www.hetzner.com/cloud — sign up (free), create a project.
Create a server:
- Location: Helsinki or Falkenstein (cheapest)
- Image: Ubuntu 22.04
- Type: CX22 (€3.79/month, 2 vCPU, 4GB RAM)
- SSH key: paste your public key (`cat ~/.ssh/id_rsa.pub`)

Note the server IP address.

- [ ] **Step 2: SSH into server and run setup**

```bash
ssh root@YOUR_SERVER_IP
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/canine-wisdom-automation/master/deploy/setup.sh | bash
```

- [ ] **Step 3: Copy credentials to server**

From your local machine:
```bash
scp .env root@YOUR_SERVER_IP:/opt/canine-wisdom/.env
scp client_secrets.json root@YOUR_SERVER_IP:/opt/canine-wisdom/client_secrets.json
scp token.json root@YOUR_SERVER_IP:/opt/canine-wisdom/token.json
scp youtube_settings.json root@YOUR_SERVER_IP:/opt/canine-wisdom/youtube_settings.json
scp -r assets/music/ root@YOUR_SERVER_IP:/opt/canine-wisdom/assets/
```

- [ ] **Step 4: Sync footage library**

```bash
rsync -avz --progress dog_footage/ root@YOUR_SERVER_IP:/opt/canine-wisdom/dog_footage/
```
This uploads your 20 clips (~800MB). Takes a few minutes.

- [ ] **Step 5: Test run on server**

```bash
ssh root@YOUR_SERVER_IP
cd /opt/canine-wisdom
docker compose run --rm pipeline
```
Watch the logs — should complete a full run and upload to YouTube.

- [ ] **Step 6: Set up daily cron**

```bash
crontab -e
```
Add this line (runs at 9am UTC daily):
```
0 9 * * * /opt/canine-wisdom/deploy/cron.sh
```

- [ ] **Step 7: Verify cron fires**

Check logs after 9am next day:
```bash
ls -la /opt/canine-wisdom/run_logs/
tail -50 /opt/canine-wisdom/run_logs/cron_*.log | head -60
```

---

## Task 5: YouTube OAuth token refresh (important for server)

The `token.json` expires and needs re-auth. On a server with no browser, this is a problem.

- [ ] **Step 1: Add token refresh detection to orchestrator**

The orchestrator already handles credential refresh. But if the token is fully revoked (not just expired), it tries to open a browser which fails on a headless server.

Add a `--headless` flag handler to `upload_youtube.py` that prints the auth URL and waits for a code to be pasted:

Read `upload_youtube.py` to find the OAuth flow and check if it already handles headless mode. If not, add:

```python
import os
if os.getenv("HEADLESS_AUTH"):
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secrets_path, SCOPES
    )
    creds = flow.run_console()  # prints URL, waits for paste
else:
    creds = flow.run_local_server(port=0)
```

Add `HEADLESS_AUTH=1` to `.env` on the server.

- [ ] **Step 2: Test re-auth on server**

```bash
ssh root@YOUR_SERVER_IP
cd /opt/canine-wisdom
HEADLESS_AUTH=1 docker compose run --rm pipeline python upload_youtube.py
```
Copy the URL, open in browser, paste the code back. New `token.json` saved.

- [ ] **Step 3: Commit**

```bash
git add upload_youtube.py
git commit -m "feat: add HEADLESS_AUTH mode for server OAuth re-authentication"
```

---

## Self-Review

| Requirement | Task |
|---|---|
| Pipeline runs automatically daily without local machine | Task 4 (cron) |
| Easy to update code | Task 2 (update.sh) + Task 3 (GitHub Actions) |
| All dependencies packaged | Task 1 (Docker) |
| Credentials never in git | Task 4 (scp credentials manually) |
| Logs visible | Task 2 (cron.sh logs to run_logs/) |
| Token refresh on headless server | Task 5 |
| Cost under $10/month | Hetzner CX22 at €3.79/month |

**Note on GPU:** The server will use CPU encoding (libx264). A full video build takes ~60s instead of ~5s with NVIDIA GPU. For a daily cron job this is fine. If speed becomes important, upgrade to a GPU instance on RunPod (~$0.20/hour spot).
