# Vaultec — Architecture Design

> Local household document vault. Priorities (ranked): **security → redundancy → backups → usability → AI**.
> Runs locally (initial target: Proxmox LXC). AI (OCR + search + Q&A) is a **core v1 requirement**.

---

## 1. Guiding principles

1. **Security first.** Documents are sensitive (IDs, contracts, medical, financial). Encrypted at rest. Least-privilege access. No plaintext leaks to logs, temp files, or search index.
2. **Redundancy.** No single disk failure loses data. Metadata and blobs both replicated/snapshotted.
3. **Recoverable.** Catastrophic-failure backups, encrypted, restorable from scratch with documented procedure. Backups tested, not just taken.
4. **Local-only by default.** No cloud dependency for core function. Cloud used only as an optional encrypted offsite backup target.
5. **AI-ready and AI-powered.** OCR text + embeddings from day one so search and Q&A work well.

---

## 2. High-level components

```
┌──────────────────────────────────────────────────────────────┐
│                         Browser (LAN)                          │
│                    Modern SPA (SvelteKit)                       │
└───────────────┬───────────────────────────────────────────────┘
                │ HTTPS (self-signed / internal CA)
┌───────────────▼───────────────────────────────────────────────┐
│                      API backend (FastAPI)                      │
│  auth · RBAC · upload · validation queue · search · AI query    │
└──┬──────────┬───────────┬───────────────┬───────────┬──────────┘
   │          │           │               │           │
┌──▼───┐  ┌───▼────┐  ┌───▼──────┐   ┌────▼─────┐ ┌───▼────────┐
│Postgres│ │Encrypted│ │Meilisearch│  │  Worker  │ │  Ollama    │
│metadata│ │ blob    │ │  / FTS    │  │ (OCR +   │ │ local LLM  │
│+pgvector│ │ store   │ │  index    │  │ embed +  │ │ (Q&A)      │
│        │ │(filesys)│ │           │  │ thumbs)  │ │            │
└────────┘ └─────────┘ └───────────┘  └──────────┘ └────────────┘
```

- **Frontend:** SvelteKit SPA — modern, fast, small footprint. Talks to API over HTTPS on LAN.
- **Backend:** FastAPI (Python). Python chosen because OCR/embedding/LLM ecosystem is Python-native → fewer moving languages.
- **Postgres + pgvector:** single source of truth for metadata, users, audit log, and vector embeddings. pgvector avoids a separate vector DB.
- **Blob store:** encrypted files on the LXC filesystem (per user's decision). Content-addressed layout.
- **Search:** Meilisearch for fast typo-tolerant full-text search over extracted text. (Alt: Postgres FTS to cut a component — see §11.)
- **Worker:** background queue (OCR → text extract → embed → thumbnail → index). Keeps API responsive.
- **Ollama:** local LLM for conversational Q&A grounded in document text (RAG).

---

## 3. Data model (initial)

```
users            (id, name, role, argon2_pw_hash, created_at, disabled)
sessions         (id, user_id, token_hash, expires_at, ip, user_agent)
documents        (id, owner_id, title, category_id, source[upload|scan],
                  status[pending|validated|rejected], mime, size_bytes,
                  blob_id, sha256, created_at, validated_by, validated_at)
document_versions(id, document_id, blob_id, sha256, created_at, created_by)
blobs            (id, path, enc_algo, size_bytes, sha256_plain, sha256_enc)
categories       (id, name, parent_id)          # nested categories
tags             (id, name)  +  document_tags
extractions      (document_id, ocr_text, lang, engine, confidence, page_count)
embeddings       (id, document_id, chunk_no, chunk_text, vector[pgvector])
validation_queue (id, document_id, submitted_by, submitted_at, note)
audit_log        (id, actor_id, action, target, meta_json, ts)   # append-only
```

Rationale: versioning built in from start (documents change). `audit_log` append-only for security forensics. `extractions` + `embeddings` separated so re-OCR/re-embed doesn't touch the document record.

---

## 4. Security model

### 4.1 Encryption at rest
- **Envelope encryption.** Each blob encrypted with a random per-file Data Encryption Key (DEK), AES-256-GCM. DEK wrapped by a Master Key (KEK).
- **KEK storage options** (decision needed — §12):
  - (a) KEK in a file readable only by service user, unlocked at boot. Simple, but disk theft + running system = exposure.
  - (b) KEK derived from an admin passphrase entered at service start (held in memory only). Strongest; requires manual unlock after reboot.
  - (c) Age/SOPS-managed key. Middle ground.
- Postgres: encrypted at rest via LUKS on the data volume (defense in depth). Sensitive columns (OCR text) live in DB — so **DB volume must be encrypted too**.
- **Search index caveat:** Meilisearch stores plaintext for search → its volume must be on the same encrypted LUKS disk. This is a real attack surface; noted for review.

### 4.2 Access control
- Roles: `admin` (manage users, validate, configure), `member` (Husband/Wife — upload, view permitted docs), optional `viewer`.
- Per-document ownership + optional sharing between household members.
- RBAC enforced in API layer, not frontend.

### 4.3 Auth
- Argon2id password hashing. Session tokens (httpOnly, secure cookies) hashed at rest.
- Optional TOTP 2FA for admin.
- Rate limiting + lockout on login.

### 4.4 Transport
- HTTPS only, even on LAN. Internal CA or self-signed cert; HSTS.

### 4.5 Hygiene
- No document content or secrets in application logs.
- Temp files for OCR written to an encrypted tmp dir, shredded after use.
- CSP, secure headers, CSRF protection on state-changing routes.

---

## 5. Storage layout (encrypted filesystem)

```
/vault
  /blobs/<sha256[0:2]>/<sha256[2:4]>/<sha256>.enc   # content-addressed, encrypted
  /tmp                                              # encrypted scratch (OCR)
/pgdata                                             # Postgres (on LUKS volume)
/models                                             # Ollama models
```

- Content-addressed (sha256 of plaintext) → automatic dedup, integrity check.
- Whole disk on a **single LUKS-encrypted volume** (ext4) = defense in depth under app-level envelope encryption. No Meilisearch dir (dropped).

---

## 6. Redundancy

> **Hardware reality:** single-SSD old ASUS laptop. **No disk mirror possible.** RAID is off the table → redundancy must come entirely from **frequent, tested backups to separate media**. The single SSD is a single point of failure; treat it as "can die any day."

- **No RAID/ZFS mirror** (one disk). Do **not** run ZFS single-disk here — its RAM appetite (ARC) competes with Postgres + Ollama on a low-RAM laptop. Use **ext4 + LUKS**.
- **Mandatory external disk:** add a cheap USB SSD/HDD as a **local backup target** (2nd copy on 2nd media). Without it there is *no* redundancy at all.
- **Snapshots:** borg/restic versioned backups give point-in-time rollback (ransomware/accidental delete) without needing filesystem snapshots.
- **DB:** nightly `pg_dump`; optional WAL archiving to the external disk for finer point-in-time recovery.

---

## 7. Backups (catastrophic recovery) — the primary safety net here

- **3-2-1:** 3 copies, 2 media, 1 offsite. On single-disk hardware this is **not optional** — it *is* the redundancy story.
- Nightly encrypted backup job:
  - Postgres logical dump (`pg_dump`).
  - Blob store copied via restic/borg over the blob dir — blobs already envelope-encrypted, so the backup target never sees plaintext.
  - Derived data (search/FTS indexes, embeddings can be recomputed) → not backed up; rebuilt from DB + blobs on restore.
- Targets: (1) **external USB disk** attached to the laptop (local, fast restore), (2) **offsite** encrypted borg repo to a second machine or cloud bucket. Keys stored separately from the vault.
- **Documented + tested restore runbook.** A backup is only real once a restore has succeeded on a clean box.

---

## 8. Scanner integration — Brother MFC-L2700-series

- **Device:** Brother MFC-L2700W (mono laser MFP). Supports **Scan-to-FTP** and **Scan-to-Network-Folder (SMB/CIFS)** configured via its built-in web UI. No reliable eSCL → **watched-folder is the right call.**
- **Plan:** run a locked-down **FTP or SMB share** inside the vault box pointed at `/vault/incoming`. Scanner pushes scans there. A **watcher** in the worker ingests new files → creates `documents` row `status=pending` → runs OCR → adds to validation queue.
- Ingest path is **untrusted**: the incoming share holds *plaintext* scans briefly → keep it on the LUKS disk, restrict to the scanner's account, and **envelope-encrypt + delete original immediately** on ingest.
- Ingested scans → `status=pending` → OCR → validation queue for a human to title/categorize/approve or reject.

---

## 9. AI pipeline (core)

```
new/validated doc
   │
   ├─ OCR (ocrmypdf + Tesseract; PDFs & images)   → extractions.ocr_text
   ├─ text chunking (by page / ~500 tokens)
   ├─ embeddings (local model via Ollama, e.g. nomic-embed-text) → pgvector
   ├─ Postgres FTS tsvector (keyword index)
   └─ thumbnail generation
```

- **Search:** hybrid — keyword (Postgres FTS `tsvector`) + semantic (pgvector cosine) → merged ranking in API.
- **Q&A (RAG):** user question → embed → top-k chunks from pgvector → prompt local LLM → answer **with citations to source documents**. No document text leaves the box.
- Runs on worker so uploads stay fast. Re-runnable if models change.
- **Hardware constraint:** CPU-only, low-RAM laptop. Use **small models** — embeddings `nomic-embed-text`; LLM `qwen2.5:3b` (or `llama3.2:3b`). OCR + embed + LLM are slow → strictly background, one job at a time, sequential queue. Q&A latency will be seconds-to-minutes; acceptable for a household vault. Larger models only if RAM allows.

---

## 10. Deployment (single ASUS laptop)

- Docker Compose on the laptop (Proxmox LXC later if moved): `api`, `worker`, `postgres`, `ollama`, `caddy` (TLS reverse proxy). No Meilisearch/Redis.
- Caddy terminates HTTPS with internal cert, proxies to API + serves SPA.
- All data volumes on the **single LUKS-encrypted ext4 disk**. External USB disk mounted for backups.
- **CPU-only Ollama** (no GPU). Consider disabling lid-sleep / setting the laptop to stay on when closed (it's a server now).
- Low RAM → cap Postgres `shared_buffers`, run one worker job at a time, keep Ollama model small so it fits alongside Postgres.

---

## 11. Tech stack summary

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | SvelteKit + TypeScript | modern, fast, lean |
| Backend | FastAPI (Python) | AI/OCR ecosystem native |
| DB | Postgres + pgvector | metadata + vectors in one |
| Blob | Encrypted filesystem, content-addressed | user decision; simple, dedup |
| Search | **Postgres FTS + pgvector** | hybrid search, no extra plaintext index |
| OCR | ocrmypdf + Tesseract | proven, local |
| Embeddings + LLM | Ollama | fully local |
| Queue/worker | **Postgres queue (SKIP LOCKED)** | no Redis; fewer parts |
| Reverse proxy/TLS | Caddy | easy internal HTTPS |
| Encryption | AES-256-GCM envelope + LUKS | app-level + disk-level |

**Decision (locked):** Meilisearch and Redis dropped for v1. Search = Postgres FTS (keyword) + pgvector (semantic), merged in API. Jobs = Postgres-backed queue via `FOR UPDATE SKIP LOCKED`. This keeps all data inside the single encrypted Postgres volume → smaller attack surface, simpler backup (no derived plaintext index to secure). Revisit Meilisearch only if FTS proves too slow at scale.

---

## 12. Decisions (resolved)

1. **KEK storage** → **passphrase at boot**, held in memory only (§4.1 option b). Security is #1; reboot leaves vault locked until admin unlocks via UI/CLI. Accepted tradeoff.
2. **Scanner integration** → **scan-to-watched-folder** (broad MFP compatibility). eSCL direct-from-UI deferred to a later phase. *Confirm scanner make/model to finalize watch protocol (SMB vs FTP vs NFS).*
3. **Lean stack** → **collapse into Postgres** (§11). Meilisearch + Redis dropped for v1.
4. **Hardware** → **single-SSD old ASUS laptop, no GPU** (confirmed). No RAID. ext4+LUKS (not ZFS). Redundancy = backups only → **external USB backup disk is mandatory** (§6/§7). LLM = small CPU models only (§9), expect slow background processing.
5. **Scanner** → **Brother MFC-L2700W**, watched-folder via FTP/SMB (§8).
6. **Offsite backup** → external USB disk (local) + encrypted borg repo offsite (second machine or cloud). *Confirm you have a USB disk + an offsite target.*

Remaining to confirm (non-blocking): laptop RAM size (sets LLM model ceiling); external USB backup disk on hand; offsite target.

---

## 13. Suggested build phases

- **P0 — Foundation:** LXC + LUKS + ZFS, Postgres, encrypted blob store, envelope encryption, auth/RBAC. (Security spine first.)
- **P1 — Core vault:** upload, categorize, version, view, search (keyword). Backups + tested restore.
- **P2 — Scanner + validation queue.**
- **P3 — AI:** OCR pipeline, embeddings, hybrid search, RAG Q&A.
- **P4 — Polish:** UI refinement, 2FA, audit views, monitoring.
```
