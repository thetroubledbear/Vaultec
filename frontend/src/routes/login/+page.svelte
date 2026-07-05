<script lang="ts">
  import { goto } from '$app/navigation';
  import { apiJson } from '$lib/api';
  import { session } from '$lib/stores/session.svelte.ts';
  import { Panel, Button } from '$lib/components';

  let username = $state('');
  let password = $state('');
  let loading = $state(false);
  let error = $state('');

  async function handleLogin() {
    error = '';

    if (!username || !password) {
      error = 'Username and password are required';
      return;
    }

    try {
      loading = true;
      const response = await apiJson<{ user: { id: string; username: string; role: string } }>(
        '/api/auth/login',
        'POST',
        { username, password }
      );

      session.setUser(response.user);
      await goto('/');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Login failed';
    } finally {
      loading = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center px-4 py-8 bg-ink font-mono">
  <div class="w-full max-w-md">
    <Panel title="TERMINAL AUTH">
      <!-- Boot text -->
      <div class="text-xs text-muted mb-6 space-y-1 leading-relaxed">
        <div><!-- ctOS v2.0 Terminal Interface --></div>
        <div class="text-cyan">&gt; Initiating secure authentication protocol...</div>
      </div>

      {#if error}
        <div class="mb-6 p-3 bg-danger bg-opacity-20 border border-danger text-danger text-xs">
          <div class="label">ERROR</div>
          <div class="mt-1">{error}</div>
        </div>
      {/if}

      <form onsubmit={(e) => { e.preventDefault(); handleLogin(); }} class="space-y-4">
        <div>
          <label class="label mb-2">USERNAME</label>
          <input
            type="text"
            bind:value={username}
            disabled={loading}
            placeholder="operator ID"
            class="input"
          />
        </div>

        <div>
          <label class="label mb-2">PASSWORD</label>
          <input
            type="password"
            bind:value={password}
            disabled={loading}
            placeholder="â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"
            class="input"
          />
        </div>

        <div class="pt-4">
          <Button variant="primary" type="submit" disabled={loading} loading={loading}>
            {loading ? 'AUTHENTICATING...' : 'AUTHENTICATE'}
          </Button>
        </div>
      </form>

      <div class="text-xs text-muted mt-6 pt-4 border-t border-line">
        <!-- Keep your credentials secure. ctOS cannot recover compromised credentials. -->
      </div>
    </Panel>
  </div>
</div>
