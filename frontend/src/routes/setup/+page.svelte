<script lang="ts">
  import { goto } from '$app/navigation';
  import { session } from '$lib/stores/session.svelte.ts';
  import { apiJson } from '$lib/api';
  import { Panel, Button } from '$lib/components';

  let passphrase = $state('');
  let passphraseConfirm = $state('');
  let adminUsername = $state('');
  let adminPassword = $state('');
  let loading = $state(false);
  let error = $state('');

  $effect.pre(() => {
    if (session.initialized) {
      goto('/login');
    }
  });

  async function handleSetup() {
    error = '';

    if (!passphrase || !passphraseConfirm || !adminUsername || !adminPassword) {
      error = 'All fields are required';
      return;
    }

    if (passphrase !== passphraseConfirm) {
      error = 'Passphrases do not match';
      return;
    }

    if (passphrase.length < 12) {
      error = 'Passphrase must be at least 12 characters';
      return;
    }

    if (adminPassword.length < 8) {
      error = 'Admin password must be at least 8 characters';
      return;
    }

    try {
      loading = true;
      await apiJson('/setup', 'POST', {
        passphrase,
        admin_name: adminUsername,
        admin_password: adminPassword
      });

      await session.refresh();
      await goto('/login');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Setup failed';
    } finally {
      loading = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center px-4 py-8 bg-ink font-mono">
  <div class="w-full max-w-md">
    <Panel title="SYSTEM INITIALIZATION">
      <!-- Boot sequence -->
      <div class="text-xs text-muted mb-6 space-y-1 leading-relaxed">
        <div><!-- ctOS v2.0 Vault Setup --></div>
        <div class="text-cyan">&gt; Initializing secure vault infrastructure...</div>
        <div class="text-cyan">&gt; Configure master credentials</div>
      </div>

      {#if error}
        <div class="mb-6 p-3 bg-danger bg-opacity-20 border border-danger text-danger text-xs">
          <div class="label">INITIALIZATION ERROR</div>
          <div class="mt-1">{error}</div>
        </div>
      {/if}

      <form onsubmit={(e) => { e.preventDefault(); handleSetup(); }} class="space-y-4">
        <div>
          <label class="label mb-2">MASTER PASSPHRASE</label>
          <input
            type="password"
            bind:value={passphrase}
            disabled={loading}
            placeholder="min 12 chars"
            class="input"
          />
        </div>

        <div>
          <label class="label mb-2">CONFIRM PASSPHRASE</label>
          <input
            type="password"
            bind:value={passphraseConfirm}
            disabled={loading}
            placeholder="confirm"
            class="input"
          />
        </div>

        <div>
          <label class="label mb-2">OPERATOR ID</label>
          <input
            type="text"
            bind:value={adminUsername}
            disabled={loading}
            placeholder="admin username"
            class="input"
          />
        </div>

        <div>
          <label class="label mb-2">OPERATOR PASSWORD</label>
          <input
            type="password"
            bind:value={adminPassword}
            disabled={loading}
            placeholder="min 8 chars"
            class="input"
          />
        </div>

        <div class="pt-4">
          <Button variant="primary" type="submit" disabled={loading} loading={loading}>
            {loading ? 'INITIALIZING...' : 'INITIALIZE VAULT'}
          </Button>
        </div>
      </form>

      <div class="text-xs text-muted mt-6 pt-4 border-t border-line">
        <!-- WARNING: Master passphrase cannot be recovered if lost. Store securely. -->
      </div>
    </Panel>
  </div>
</div>
