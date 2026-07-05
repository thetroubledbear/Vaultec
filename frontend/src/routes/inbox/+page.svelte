<script lang="ts">
  import { session } from '$lib/stores/session.svelte.ts';
  import { apiJson, contentUrl } from '$lib/api';
  import { formatFileSize, formatDate } from '$lib/utils';
  import Panel from '$lib/components/Panel.svelte';
  import Button from '$lib/components/Button.svelte';
  import StatusDot from '$lib/components/StatusDot.svelte';

  interface ValidationItem {
    queue_id: string;
    document_id: string;
    title: string;
    filename: string;
    mimetype: string;
    size_bytes: number;
    created_at: string;
  }

  interface AdminUser {
    id: string;
    username: string;
    role: string;
    is_active: boolean;
  }

  let items = $state<ValidationItem[]>([]);
  let adminUsers = $state<AdminUser[]>([]);
  let loading = $state(false);
  let error = $state('');
  let submittingId = $state<string | null>(null);
  let submittingError = $state<Record<string, string>>({});

  // Form state per item
  let formData = $state<
    Record<
      string,
      {
        title: string;
        category: string;
        owner_id?: string;
      }
    >
  >({});

  async function loadItems() {
    try {
      loading = true;
      error = '';
      const response = await apiJson<{ items: ValidationItem[] }>('/api/validation/');
      items = response.items;
      // Initialize form data for each item
      items.forEach(item => {
        if (!formData[item.document_id]) {
          formData[item.document_id] = {
            title: item.title,
            category: '',
            owner_id: undefined
          };
        }
      });
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load validation items';
    } finally {
      loading = false;
    }
  }

  async function loadAdminUsers() {
    if (session.user?.role !== 'admin') return;
    try {
      adminUsers = await apiJson<AdminUser[]>('/api/admin/users');
      adminUsers = adminUsers.filter(u => u.is_active);
    } catch (err) {
      console.error('Failed to load admin users:', err);
    }
  }

  $effect.pre(async () => {
    if (session.isAuthenticated && session.unlocked) {
      await loadItems();
      await loadAdminUsers();
    }
  });

  async function approve(documentId: string) {
    const form = formData[documentId];
    if (!form) return;

    try {
      submittingId = documentId;
      submittingError[documentId] = '';

      const payload: Record<string, unknown> = {
        title: form.title
      };
      if (form.category.trim()) {
        payload.category = form.category.trim();
      }
      if (session.user?.role === 'admin' && form.owner_id) {
        payload.owner_id = form.owner_id;
      }

      await apiJson(`/api/validation/${documentId}/approve`, 'POST', payload);
      // Remove from list
      items = items.filter(item => item.document_id !== documentId);
      delete formData[documentId];
    } catch (err) {
      submittingError[documentId] = err instanceof Error ? err.message : 'Approval failed';
    } finally {
      submittingId = null;
    }
  }

  async function reject(documentId: string) {
    if (!confirm('Are you sure you want to reject this scan? It will be discarded.')) return;

    try {
      submittingId = documentId;
      submittingError[documentId] = '';
      await apiJson(`/api/validation/${documentId}/reject`, 'POST');
      // Remove from list
      items = items.filter(item => item.document_id !== documentId);
      delete formData[documentId];
    } catch (err) {
      submittingError[documentId] = err instanceof Error ? err.message : 'Rejection failed';
    } finally {
      submittingId = null;
    }
  }

  function getPreviewComponent(mimetype: string, documentId: string) {
    if (mimetype === 'application/pdf') {
      return 'pdf';
    } else if (mimetype.startsWith('image/')) {
      return 'image';
    } else if (mimetype.startsWith('text/')) {
      return 'text';
    }
    return 'none';
  }
</script>

<div class="max-w-6xl mx-auto px-4 py-8">
  {#if !session.unlocked}
    <div class="mb-8 p-6 bg-amber-50 dark:bg-amber-900/20 border-2 border-amber-200 dark:border-amber-800 rounded-lg">
      <h2 class="text-lg font-semibold text-amber-900 dark:text-amber-200 mb-2">🔒 Vault is Locked</h2>
      <p class="text-amber-800 dark:text-amber-300 mb-4">
        Your vault has been locked. Use the Unlock button in the top bar to unlock it with your master passphrase.
      </p>
    </div>
  {:else}
    <!-- Header -->
    <Panel title="// VALIDATION QUEUE" subtitle="({items.length} pending)">
      <p class="text-muted text-xs">Review and approve documents before they enter your library.</p>
    </Panel>

    {#if error}
      <div class="mb-6 p-4 border border-danger text-danger text-sm">
        {error}
      </div>
    {/if}

    {#if loading}
      <div class="p-8 text-center">
        <div class="inline-block animate-spin text-4xl">⏳</div>
        <p class="mt-2 text-muted">Loading validation queue...</p>
      </div>
    {:else if items.length === 0}
      <Panel title="INBOX ZERO">
        <div class="text-center py-8">
          <div class="text-6xl mb-4">✨</div>
          <p class="text-muted text-sm">No scans waiting for review. Check back later!</p>
        </div>
      </Panel>
    {:else}
      <div class="space-y-4 mt-8">
        {#each items as item (item.document_id)}
          <Panel title={item.title.toUpperCase()}>
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <!-- Preview Section -->
              <div class="lg:col-span-1">
                <div class="border border-line bg-panel-light rounded overflow-hidden flex items-center justify-center h-48">
                  {#if getPreviewComponent(item.mimetype, item.document_id) === 'pdf'}
                    <iframe
                      src={contentUrl(item.document_id)}
                      class="w-full h-full border-0"
                      title={item.filename}
                    />
                  {:else if getPreviewComponent(item.mimetype, item.document_id) === 'image'}
                    <img
                      src={contentUrl(item.document_id)}
                      alt={item.filename}
                      class="w-full h-full object-cover"
                    />
                  {:else if getPreviewComponent(item.mimetype, item.document_id) === 'text'}
                    <div class="w-full h-full p-4 overflow-auto bg-ink text-xs text-muted font-mono">
                      <p class="text-center">[Text preview not shown]</p>
                      <p class="text-center text-xs mt-2">{item.filename}</p>
                    </div>
                  {:else}
                    <div class="text-center">
                      <div class="text-4xl mb-2">📎</div>
                      <p class="text-sm text-muted">{item.filename}</p>
                    </div>
                  {/if}
                </div>
                <div class="mt-3 space-y-1 text-xs text-muted font-mono">
                  <p><span class="text-bright">Size:</span> {formatFileSize(item.size_bytes)}</p>
                  <p><span class="text-bright">Type:</span> {item.mimetype}</p>
                  <p><span class="text-bright">Received:</span> {formatDate(item.created_at)}</p>
                </div>
              </div>

              <!-- Form Section -->
              <div class="lg:col-span-2">
                <h3 class="label mb-4">REVIEW & APPROVE</h3>

                {#if submittingError[item.document_id]}
                  <div class="mb-4 p-3 border border-danger text-danger text-sm">
                    {submittingError[item.document_id]}
                  </div>
                {/if}

                <div class="space-y-4">
                  <!-- Title -->
                  <div>
                    <div class="label mb-2">Title *</div>
                    <input
                      type="text"
                      bind:value={formData[item.document_id].title}
                      disabled={submittingId === item.document_id}
                      class="input w-full text-sm disabled:opacity-50"
                    />
                  </div>

                  <!-- Category -->
                  <div>
                    <div class="label mb-2">Category (optional)</div>
                    <input
                      type="text"
                      bind:value={formData[item.document_id].category}
                      disabled={submittingId === item.document_id}
                      placeholder="e.g., Tax, Insurance, Medical"
                      class="input w-full text-sm disabled:opacity-50"
                    />
                  </div>

                  <!-- Owner Selection (admin only) -->
                  {#if session.user?.role === 'admin'}
                    <div>
                      <div class="label mb-2">Owner (optional)</div>
                      <select
                        bind:value={formData[item.document_id].owner_id}
                        disabled={submittingId === item.document_id}
                        class="input w-full text-sm disabled:opacity-50"
                      >
                        <option value="">Select owner...</option>
                        {#each adminUsers as user (user.id)}
                          <option value={user.id}>{user.username}</option>
                        {/each}
                      </select>
                    </div>
                  {/if}

                  <!-- Actions -->
                  <div class="flex gap-3 pt-2">
                    <Button
                      onclick={() => approve(item.document_id)}
                      disabled={submittingId === item.document_id}
                      variant="success"
                    >
                      {submittingId === item.document_id ? '[ APPROVING... ]' : '[ APPROVE ]'}
                    </Button>
                    <Button
                      onclick={() => reject(item.document_id)}
                      disabled={submittingId === item.document_id}
                      variant="danger"
                    >
                      {submittingId === item.document_id ? '[ REJECTING... ]' : '[ REJECT ]'}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </Panel>
        {/each}
      </div>
    {/if}
  {/if}
</div>
