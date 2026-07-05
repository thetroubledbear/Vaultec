# Vaultec Frontend

A modern SvelteKit frontend for Vaultec, a secure document vault.

## Quick Start

```bash
npm install
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies API calls to `http://localhost:8000`.

## Stack

- **SvelteKit 2** with Svelte 5 (runes syntax)
- **TypeScript** for type safety
- **Tailwind CSS 3** for styling
- **Vite** for fast bundling

## Architecture

- `src/routes/` — SvelteKit pages (setup, login, dashboard)
- `src/lib/stores/session.svelte.ts` — Reactive session & auth state
- `src/lib/api.ts` — HTTP client with JSON/multipart/download helpers
- `src/lib/utils.ts` — File size and date formatting utilities
- `vite.config.ts` — Proxies `/api`, `/health`, `/setup`, `/unlock` to backend

## Features

- First-run initialization wizard
- User authentication
- Document upload (with title & optional category)
- Document listing & download
- Vault lock/unlock mechanism
- Dark mode support
- Responsive design

## Notes

- The Vite dev proxy includes `credentials: 'include'` for session cookies
- All API endpoints use relative paths (e.g., `/api/documents/`)
- The adapter is configured as an SPA with static output
- No server-side rendering (SSR disabled)
