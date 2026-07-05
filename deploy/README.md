# Vaultec Production Deployment Guide

This guide covers deploying Vaultec to a Debian/Ubuntu Linux home server (e.g., an old laptop).

## Prerequisites

- **OS**: Debian 11+, Ubuntu 22.04+, or similar
- **RAM**: 2+ GB (4+ GB recommended if using ollama)
- **Disk**: 20+ GB free (100+ GB if storing encrypted blobs)
- **Network**: Static IP or DHCP reservation recommended
- **SSH access** (for install and management)

## Quick Start

### 1. Clone/download Vaultec repo and cd into it

```bash
cd /path/to/vaultec
```

### 2. Run the installer

```bash
sudo bash deploy/install.sh
```

**Optional**: To enable AI features (Ollama), use the `--with-ai` flag:

```bash
sudo bash deploy/install.sh --with-ai
```

The installer will:
- Detect the OS and require root
- Install Docker + docker-compose plugin if missing
- Generate a `.env` file with secure defaults (POSTGRES_PASSWORD auto-generated)
- Build the frontend SPA in a container (no Node required on host)
- Build and start the docker-compose stack (db, api, worker, caddy)
- Optionally pull and start Ollama with small models

**Expected time**: 3–10 minutes (varies by hardware and network)

### 3. Access the web UI

After the installer finishes, you'll see **NEXT STEPS**:

1. Find your server's IP:
   ```bash
   hostname -I
   ```

2. Open in a browser (**accept the self-signed certificate**):
   ```
   https://<server-ip>/
   ```
   or if DNS is set up:
   ```
   https://vaultec.local/
   ```
   
   Caddy uses internal TLS (self-signed) on a LAN, so you must accept the security warning.

### 4. Initial Setup (First Run)

The vault starts **LOCKED**. Create the admin account and master passphrase:

```bash
curl -X POST https://<server-ip>/setup \
  -H 'Content-Type: application/json' \
  -d '{"admin_username": "admin", "master_passphrase": "your-secure-phrase"}' \
  -k  # Accept self-signed certificate
```

Then log in via the web UI with the credentials above.

### 5. After Every Reboot: Unlock the Vault

The vault automatically locks after system shutdown. Unlock it:

```bash
curl -X POST https://<server-ip>/unlock \
  -H 'Content-Type: application/json' \
  -d '{"master_passphrase": "your-secure-phrase"}' \
  -k
```

Or use the web UI unlock page.

---

## Data and Storage

### Volume Locations

Docker volumes are stored in `/var/lib/docker/volumes/`. Key volumes:
- **pgdata**: PostgreSQL database
- **vaultblobs**: Encrypted blob storage (envelopes already encrypted at app level)
- **vaulttmp**: Temporary files
- **ollama_models**: Ollama model cache (if enabled)
- **caddy_data**, **caddy_config**: Caddy TLS certs and config

### LUKS Encryption (Highly Recommended for Production)

Since this is a home server, **strongly encrypt the storage volumes** with LUKS:

#### Option A: Encrypt the entire Docker data root (simplest)

1. **Prepare a new disk/partition** (e.g., `/dev/sdb1`, at least 50 GB)

2. **Create LUKS volume**:
   ```bash
   sudo cryptsetup luksFormat /dev/sdb1
   sudo cryptsetup luksOpen /dev/sdb1 vaultec-storage
   sudo mkfs.ext4 /dev/mapper/vaultec-storage
   sudo mkdir -p /mnt/vaultec-storage
   sudo mount /dev/mapper/vaultec-storage /mnt/vaultec-storage
   sudo chown docker:docker /mnt/vaultec-storage
   ```

3. **Configure Docker to use this mount as its data root**:
   ```bash
   sudo systemctl stop docker
   sudo vi /etc/docker/daemon.json
   ```
   Add or modify:
   ```json
   {
     "data-root": "/mnt/vaultec-storage/docker"
   }
   ```
   ```bash
   sudo systemctl start docker
   ```

4. **Auto-unlock on boot** (optional, via crypttab):
   - Create a keyfile: `sudo dd if=/dev/urandom of=/root/.luks-key bs=32 count=1`
   - Add to `/etc/crypttab`: `vaultec-storage /dev/sdb1 /root/.luks-key luks`
   - Lock down: `sudo chmod 400 /root/.luks-key`

#### Option B: Mount encrypted volumes under Docker volumes dir

More granular but requires script automation—see your Docker documentation for details.

---

## Backups

### Automated Backup Script

A backup script is provided: `deploy/backup.sh`

It performs:
1. **SQL dump** of the PostgreSQL database (gzipped, stored locally)
2. **BorgBackup** snapshot (if configured) of dumps + blobs to remote storage

#### Local Backups Only

```bash
bash deploy/backup.sh
```

Dumps are saved to `backups/` locally. Rotate manually or use cron:

```bash
# Daily at 2 AM
0 2 * * * cd /path/to/vaultec && bash deploy/backup.sh
```

#### Remote Backups with BorgBackup

Install borg on the server:
```bash
sudo apt install borgbackup
```

Initialize a borg repo (local or remote SSH):
```bash
borg init --encryption=repokey-aes-ocb /path/to/borg-repo
```

Run backup with borg enabled:
```bash
BORG_REPO=/path/to/borg-repo BORG_PASSPHRASE=secret bash deploy/backup.sh
```

In cron (example for daily 2 AM):
```bash
0 2 * * * export BORG_REPO=/path/to/borg-repo BORG_PASSPHRASE=secret; cd /path/to/vaultec && bash deploy/backup.sh
```

**Note**: Blobs are already envelope-encrypted at the application level, so the backup target (and borg repo) never see plaintext data.

### Restore Procedure

1. **Database**: Restore a SQL dump:
   ```bash
   docker compose exec -T db psql -U vaultec vaultec < backups/vaultec_db_YYYYMMDD_HHMMSS.sql
   gunzip -c backups/vaultec_db_YYYYMMDD_HHMMSS.sql.gz | \
     docker compose exec -T db psql -U vaultec vaultec
   ```

2. **Blobs**: If using borg, extract the archive:
   ```bash
   cd /tmp
   borg extract /path/to/borg-repo::archive-name
   # Copy blobs volume content back to /var/lib/docker/volumes/vaultec_vaultblobs/_data/
   ```

---

## Management & Monitoring

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f db
```

### Service Health

```bash
# List running containers
docker compose ps

# API health check
curl http://localhost:8000/health
```

### Restart Services

```bash
# Restart the stack
docker compose restart

# Restart specific service
docker compose restart api
```

### Stop Services

```bash
docker compose down  # Stops all, keeps volumes
docker compose down -v  # Stops all, REMOVES volumes (destructive!)
```

### Auto-Start on Boot

Restart policies are already set to `unless-stopped`. Enable the Docker service on boot:

```bash
sudo systemctl enable docker
sudo systemctl is-enabled docker  # Verify
```

Container restart after reboot:
1. System boots → Docker daemon starts (via systemd)
2. Docker restarts containers with `restart: unless-stopped`
3. Services come online automatically

---

## Network & HTTPS

### Internal TLS (Self-Signed)

Caddy uses `tls internal` to generate self-signed certificates on a LAN. This works without public DNS or Let's Encrypt:

- **Site address**: `:443` (all interfaces on port 443)
- **TLS**: Internal self-signed (regenerated each time Caddy starts)
- **Access**: `https://<server-ip>/` or `https://vaultec.local/`

### Add DNS (Optional)

If you have local DNS (e.g., dnsmasq, AdGuard Home):
- Add A record: `vaultec.local -> <server-ip>`
- Accessing `https://vaultec.local/` avoids typing the IP

### Allow External Access (Advanced)

If you want Vaultec accessible from outside the LAN:
1. Port-forward 443 to the home server in your router
2. Use a dynamic DNS service or static public IP
3. (Optional) Replace `tls internal` with a proper CA (Let's Encrypt via ACME)

---

## Troubleshooting

### API not healthy / won't start

Check logs:
```bash
docker compose logs api
```

Common issues:
- **Database not ready**: Wait a few seconds, the healthcheck takes time
- **Port 8000 in use**: Check `lsof -i :8000` or change docker-compose port mapping
- **Migrations failed**: Check `docker compose logs db` for corruption

### Frontend not loading / 404

Ensure `frontend/build/index.html` exists:
```bash
ls -la frontend/build/
```

If missing, rebuild:
```bash
docker run --rm -v "$PWD/frontend":/app -w /app node:20-alpine sh -c "npm ci && npm run build"
```

### HTTPS certificate errors

Self-signed certs are expected. In curl, use `-k` flag. In browsers, click "Advanced" → "Proceed anyway" (exact steps vary by browser).

### Out of disk space

Check Docker volumes:
```bash
docker system df
```

If ollama models are filling disk, remove unused models or increase storage.

### After update / pull new code

1. Rebuild images:
   ```bash
   docker compose build
   ```

2. Restart services:
   ```bash
   docker compose up -d
   ```

3. Migrations run automatically on API start (see `backend/entrypoint.sh`)

---

## Advanced: Development Mode

For local development, use `APP_ENV=dev` in `.env`:

```bash
APP_ENV=dev
DATABASE_URL=postgresql://vaultec:vaultec_dev_password@localhost:5432/vaultec
```

Then run:
```bash
# Terminal 1: services
docker compose up -d db api

# Terminal 2: frontend dev server
cd frontend && npm run dev
```

(No Caddy/HTTPS needed for dev—frontend dev server proxies API locally.)

---

## Support & Updates

- Repository: [Vaultec GitHub](https://github.com/your-org/vaultec)
- Issues: [GitHub Issues](https://github.com/your-org/vaultec/issues)
- Docs: See `/docs` in the repo

---

**Last Updated**: 2026-07-04
