# Vaultec

A local household document-vault app with end-to-end encryption.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full technical specification.

## Security First

- **Envelope Encryption**: Per-file AES-256-GCM DEK wrapped by a master KEK
- **Master Passphrase**: Derived via Argon2id, held only in memory (vault locks on reboot)
- **Postgres + pgvector**: Secure queryable encrypted storage with vector embeddings
- **Encrypted Filesystem**: All blobs stored on LUKS-encrypted ZFS

## P0 Host Setup Checklist

1. **Create LUKS-encrypted ZFS mirror dataset**
   - Mount at `/vault` with `chmod 700`

2. **Mount volumes on encrypted dataset**
   - Ensure `VAULT_BLOB_DIR` and `VAULT_TMP_DIR` reside on encrypted ZFS

3. **Set environment variables**
   - Copy `.env.example` to `.env` and configure `DATABASE_URL`, vault paths, etc.

4. **Start services**
   ```bash
   docker-compose up -d
   ```

5. **First-run: unlock the vault**
   - Call `POST /unlock` with admin passphrase
   - Master KEK is derived and held in memory until reboot

## Security Notes

- **Vault is locked after reboot** until the admin passphrase is entered at `/unlock`
- No plaintext keys or passphrases are logged
- Database user should have minimal privileges; consider network isolation for Postgres
