# Vaultec Backend

FastAPI backend for Vaultec: secure document vault with envelope encryption.

## Quick Start

1. Copy `.env.example` to `.env` (in project root):
   ```bash
   cp ../.env.example ../.env
   ```

2. Start services with Docker Compose:
   ```bash
   docker compose up --build
   ```

3. Check health (vault is locked by default):
   ```bash
   curl http://localhost:8000/health
   ```
   Expected response:
   ```json
   {"status":"ok","initialized":false,"unlocked":false}
   ```

4. Initialize vault and create admin user (one-time):
   ```bash
   curl -X POST http://localhost:8000/setup \
     -H "Content-Type: application/json" \
     -d '{
       "passphrase": "your_master_passphrase",
       "admin_name": "admin",
       "admin_password": "admin_password"
     }'
   ```

5. After every restart, unlock the vault:
   ```bash
   curl -X POST http://localhost:8000/unlock \
     -H "Content-Type: application/json" \
     -d '{"passphrase": "your_master_passphrase"}'
   ```

## Architecture

- **Vault Lifecycle**: Vault boots LOCKED. Call `/setup` once to initialize, then `/unlock` after each restart.
- **Envelope Encryption**: Master KEK (Key Encryption Key) derived from passphrase via Argon2id. Each blob has its own DEK (Data Encryption Key) wrapped by KEK. AES-256-GCM for all encryption.
- **Database**: PostgreSQL with pgvector extension for embeddings.
- **Migrations**: Alembic manages schema. Entrypoint runs `alembic upgrade head` automatically.

## Files

- `app/main.py` — FastAPI app and endpoints
- `app/config.py` — Settings from environment
- `app/db.py` — SQLAlchemy session factory
- `app/models.py` — ORM models (all tables)
- `app/crypto.py` — Envelope encryption core
- `app/security.py` — Password hashing (Argon2id)
- `app/vault.py` — Vault lifecycle (initialize, unlock, verification)
- `migrations/` — Alembic migrations
- `entrypoint.sh` — Container startup (waits for DB, runs migrations, starts uvicorn)
- `Dockerfile` — Container image
