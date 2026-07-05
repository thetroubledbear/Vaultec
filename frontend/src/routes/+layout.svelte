<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { session } from '$lib/stores/session.svelte';
  import { validation } from '$lib/stores/validation.svelte';
  import { theme } from '$lib/stores/theme.svelte';
  import { apiJson } from '$lib/api';
  import { Button, Badge, StatusDot } from '$lib/components';
  import '../app.css';

  let mounted = $state(false);
  let isLocking = $state(false);

  $effect.pre(async () => {
    if (!mounted) {
      mounted = true;
      theme.init();
      await session.refresh();

      if (!session.initialized) {
        await goto('/setup');
      } else if (!session.isAuthenticated && $page.url.pathname !== '/setup') {
        await goto('/login');
      }
    }
  });

  // Refresh validation count when authenticated and unlocked
  $effect.pre(async () => {
    if (session.isAuthenticated && session.unlocked) {
      await validation.refresh();
    }
  });

  async function handleLogout() {
    try {
      await apiJson('/api/auth/logout', 'POST');
      session.setUser(null);
      await goto('/login');
    } catch (err) {
      console.error('Logout failed:', err);
    }
  }

  async function handleUnlock() {
    const passphrase = prompt('Enter passphrase to unlock vault:');
    if (!passphrase) return;

    try {
      isLocking = true;
      await apiJson('/unlock', 'POST', { passphrase });
      await session.refresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Unlock failed');
    } finally {
      isLocking = false;
    }
  }
</script>

<div class="min-h-screen flex flex-col bg-ink text-bright font-mono overflow-hidden">
  {#if mounted}
    {#if session.isAuthenticated && $page.url.pathname !== '/setup' && $page.url.pathname !== '/login'}
      <!-- ctOS HUD Header -->
      <header class="border-b border-line bg-panel/50 backdrop-blur-sm">
        <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <!-- Brand -->
          <div class="flex items-center gap-2 flex-shrink-0">
            <div class="w-6 h-6 border border-cyan flex items-center justify-center text-cyan text-xs font-bold">V</div>
            <span class="text-xs uppercase tracking-widest text-cyan glow-cyan">VAULTEC // File System</span>
          </div>

          <!-- Center: Vault Status -->
          <div class="flex-1 flex items-center justify-center">
            {#if session.health}
              <div class="flex items-center gap-2">
                {#if session.unlocked}
                  <Badge text="UNLOCKED" tone="success" />
                {:else}
                  <Badge text="LOCKED" tone="amber" />
                {/if}
              </div>
            {/if}
          </div>

          <!-- Right: Nav & User -->
          <div class="flex items-center gap-3 flex-shrink-0">
            <!-- Nav Links as Tabs -->
            <nav class="flex items-center gap-1 border-l border-line pl-3">
              <a
                href="/"
                class="px-2 py-1 text-xs uppercase tracking-wider border border-line text-normal hover:text-cyan hover:border-cyan transition-colors {$page.url.pathname === '/' ? 'border-cyan text-cyan' : ''}"
              >
                VAULT
              </a>
              <a
                href="/inbox"
                class="relative px-2 py-1 text-xs uppercase tracking-wider border border-line text-normal hover:text-cyan hover:border-cyan transition-colors {$page.url.pathname === '/inbox' ? 'border-cyan text-cyan' : ''}"
              >
                INBOX
                {#if validation.pending > 0}
                  <span class="absolute -top-1 -right-1 w-3 h-3 bg-danger rounded-full text-white text-xs flex items-center justify-center leading-none">
                    {validation.pending}
                  </span>
                {/if}
              </a>
              <a
                href="/search"
                class="px-2 py-1 text-xs uppercase tracking-wider border border-line text-normal hover:text-cyan hover:border-cyan transition-colors {$page.url.pathname === '/search' ? 'border-cyan text-cyan' : ''}"
              >
                SEARCH
              </a>
              <a
                href="/settings"
                class="px-2 py-1 text-xs uppercase tracking-wider border border-line text-normal hover:text-cyan hover:border-cyan transition-colors {$page.url.pathname === '/settings' ? 'border-cyan text-cyan' : ''}"
              >
                CONFIG
              </a>
            </nav>

            <!-- Operator Info -->
            {#if session.user}
              <div class="flex items-center gap-2 border-l border-line pl-3">
                <span class="text-xs text-muted uppercase tracking-wider">OP:</span>
                <span class="text-xs text-bright uppercase tracking-wider">{session.user.username}</span>
              </div>
            {/if}

            <!-- Theme toggle -->
            <Button variant="ghost" onclick={() => theme.toggle()}>
              {theme.value === 'dark' ? '☀ LIGHT' : '☾ DARK'}
            </Button>

            <!-- Unlock Button -->
            {#if session.health && !session.unlocked}
              <Button variant="primary" disabled={isLocking} onclick={handleUnlock}>
                {isLocking ? 'UNLOCKING...' : 'UNLOCK'}
              </Button>
            {/if}

            <!-- Logout -->
            <Button variant="danger" onclick={handleLogout}>
              EXIT
            </Button>
          </div>
        </div>
      </header>
    {/if}

    <main class="flex-1 overflow-auto">
      <div class="grid-bg min-h-full">
        <slot />
      </div>
    </main>
  {/if}
</div>
