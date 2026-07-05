#!/usr/bin/env bash
set -euo pipefail

# Vaultec Backup Script
# Backs up PostgreSQL database and (optionally) the encrypted blob volume via BorgBackup
# Usage: deploy/backup.sh
# Environment variables:
#   BORG_REPO      - Path or SSH location for borg repo (optional)
#   BORG_PASSPHRASE - Passphrase for borg repo (optional, prompted if not set)
#   POSTGRES_USER   - Database user (default: vaultec, from docker-compose .env)
#   POSTGRES_DB     - Database name (default: vaultec, from docker-compose .env)

LOG_PREFIX="[vaultec-backup]"

log() {
    echo "$LOG_PREFIX $*"
}

log_info() {
    echo "$LOG_PREFIX [info] $*"
}

log_warn() {
    echo "$LOG_PREFIX [warn] $*"
}

log_error() {
    echo "$LOG_PREFIX [error] $*" >&2
}

# Determine script location and move to repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

log "Backup starting..."

# Load .env to get database credentials (docker-compose reads this automatically)
if [[ -f .env ]]; then
    set +u
    source .env
    set -u
else
    log_error ".env file not found"
    exit 1
fi

# Set defaults if not in .env
POSTGRES_USER="${POSTGRES_USER:-vaultec}"
POSTGRES_DB="${POSTGRES_DB:-vaultec}"

# Create backups directory if it doesn't exist
BACKUPS_DIR="$REPO_ROOT/backups"
mkdir -p "$BACKUPS_DIR"
log_info "Backups directory: $BACKUPS_DIR"

# Timestamp for the backup file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SQL_DUMP="$BACKUPS_DIR/vaultec_db_${TIMESTAMP}.sql.gz"

# Step 1: Dump PostgreSQL database
log "Dumping PostgreSQL database..."
if docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$SQL_DUMP"; then
    log_info "Database dump saved: $SQL_DUMP"
    # Show file size
    SIZE=$(du -h "$SQL_DUMP" | cut -f1)
    log_info "Dump size: $SIZE"
else
    log_error "Database dump failed"
    exit 1
fi

# Step 1b: Dump the encrypted blob store. Blobs live in the 'vaultblobs' Docker volume,
# mounted in the api container at VAULT_BLOB_DIR. We stream a tarball out of the running
# container so we don't need to know the raw volume path. Blobs are already envelope-
# encrypted (AES-256-GCM), so this tarball contains only ciphertext.
BLOB_DIR="${VAULT_BLOB_DIR:-/vault/blobs}"
BLOB_DUMP="$BACKUPS_DIR/vaultec_blobs_${TIMESTAMP}.tar.gz"
log "Dumping encrypted blob store from $BLOB_DIR ..."
if docker compose exec -T api tar czf - -C "$BLOB_DIR" . > "$BLOB_DUMP"; then
    BSIZE=$(du -h "$BLOB_DUMP" | cut -f1)
    log_info "Blob dump saved: $BLOB_DUMP ($BSIZE)"
else
    log_error "Blob dump failed — WITHOUT blobs the backup is incomplete. Aborting."
    rm -f "$BLOB_DUMP"
    exit 1
fi

# Step 2: BorgBackup (if configured)
if [[ -n "${BORG_REPO:-}" ]]; then
    log "BorgBackup is configured, backing up to: $BORG_REPO"

    # Check if borg is available
    if ! command -v borg &> /dev/null; then
        log_warn "borg command not found, skipping borg backup. Install BorgBackup to enable:"
        log_warn "  sudo apt install borgbackup"
    else
        # Ensure BORG_PASSPHRASE is set (prompt if not)
        if [[ -z "${BORG_PASSPHRASE:-}" ]]; then
            log "BorgBackup requires a passphrase."
            read -sp "Enter BORG_PASSPHRASE: " BORG_PASSPHRASE
            echo
        fi
        export BORG_PASSPHRASE

        # Initialize repo if it doesn't exist
        if ! borg list "$BORG_REPO" &> /dev/null; then
            log_info "Initializing new borg repository: $BORG_REPO"
            borg init --encryption=repokey-aes-ocb "$BORG_REPO"
        fi

        # Create backup archive
        ARCHIVE_NAME="vaultec_${TIMESTAMP}"
        log "Creating borg archive: $ARCHIVE_NAME"
        # Include SQL dump and the encrypted blob volume
        # Note: blobs are already envelope-encrypted, so backup target sees only ciphertext
        if borg create \
            "$BORG_REPO"::"$ARCHIVE_NAME" \
            "$BACKUPS_DIR" \
            --progress \
            --stats; then
            log_info "Borg archive created: $ARCHIVE_NAME"
        else
            log_error "Borg archive creation failed"
            exit 1
        fi

        # Prune old backups (retention policy)
        log "Pruning old backups (retention: daily 7, weekly 4, monthly 6)..."
        if borg prune \
            "$BORG_REPO" \
            --keep-daily 7 \
            --keep-weekly 4 \
            --keep-monthly 6 \
            --progress \
            --stats; then
            log_info "Borg prune complete"
        else
            log_warn "Borg prune failed (continuing)"
        fi

        unset BORG_PASSPHRASE
    fi
else
    log_info "BORG_REPO not set, skipping remote backup."
    log_info "To enable BorgBackup:"
    log_info "  1. Install: sudo apt install borgbackup"
    log_info "  2. Initialize a borg repo: borg init --encryption=repokey-aes-ocb /path/to/backup"
    log_info "  3. Export in cron: export BORG_REPO=/path/to/backup BORG_PASSPHRASE=<secret>"
    log_info "  4. Run this script: deploy/backup.sh"
    log_info ""
    log_info "Local SQL dumps are kept in: $BACKUPS_DIR"
fi

log "Backup complete!"
