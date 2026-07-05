<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { apiJson, ApiError, contentUrl, downloadUrl, apiDownload } from '$lib/api';
  import { formatFileSize, formatDate } from '$lib/utils';
  import { session } from '$lib/stores/session.svelte.ts';
  import Panel from '$lib/components/Panel.svelte';
  import Button from '$lib/components/Button.svelte';
  import Badge from '$lib/components/Badge.svelte';

  interface DocumentMeta {
    id: string;
    title: string;
    created_at: string;
    category?: string | null;
    owner_id: string;
    owner_username: string | null;
    is_owner: boolean;
    household_id?: string | null;
    blob: {
      filename: string;
      mimetype: string;
      size_bytes: number;
    };
  }

  let doc = $state<DocumentMeta | null>(null);
  let contentText = $state('');
  let loading = $state(true);
  let error = $state('');
  let editingTitle = $state(false);
  let newTitle = $state('');
  let editingCategory = $state(false);
  let newCategory = $state('');
  let updateLoading = $state(false);
  let updateError = $state('');

  const docId = $page.params.id;

  async function loadDocument() {
    try {
      loading = true;
      error = '';
      const response = await apiJson<DocumentMeta>(`/api/documents/${docId}`);
      doc = response;
      newTitle = response.title;
      newCategory = response.category || '';

      // Load text content if applicable
      if (response.blob.mimetype.startsWith('text/')) {
        try {
          const contentResponse = await fetch(contentUrl(docId), {
            credentials: 'include'
          });
          if (contentResponse.ok) {
            contentText = await contentResponse.text();
          }
        } catch (err) {
          console.error('Failed to load text content:', err);
        }
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        error = 'Document not found';
      } else if (err instanceof ApiError && err.status === 403) {
        error = 'Access denied';
      } else {
        error = err instanceof Error ? err.message : 'Failed to load document';
      }
    } finally {
      loading = false;
    }
  }

  $effect.pre(() => {
    loadDocument();
  });

  async function handleUpdateTitle() {
    if (!doc || !newTitle.trim()) return;

    try {
      updateLoading = true;
      updateError = '';
      await apiJson(`/api/documents/${docId}`, 'PATCH', {
        title: newTitle.trim()
      });
      doc.title = newTitle.trim();
      editingTitle = false;
    } catch (err) {
      updateError = err instanceof Error ? err.message : 'Failed to update title';
    } finally {
      updateLoading = false;
    }
  }

  async function handleUpdateCategory() {
    if (!doc) return;

    try {
      updateLoading = true;
      updateError = '';
      await apiJson(`/api/documents/${docId}`, 'PATCH', {
        category: newCategory.trim() || null
      });
      doc.category = newCategory.trim() || undefined;
      editingCategory = false;
    } catch (err) {
      updateError = err instanceof Error ? err.message : 'Failed to update category';
    } finally {
      updateLoading = false;
    }
  }

  async function handleDownload() {
    if (!doc) return;
    try {
      const blob = await apiDownload(downloadUrl(docId));
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.blob.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Download failed');
    }
  }

  async function handleDelete() {
    if (!confirm('Are you sure you want to delete this document? This cannot be undone.')) return;

    try {
      await apiJson(`/api/documents/${docId}`, 'DELETE');
      await goto('/');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    }
  }

  function getPreviewComponent() {
    if (!doc) return null;
    const { mimetype } = doc.blob;

    if (mimetype === 'application/pdf') {
      return 'pdf';
    } else if (mimetype.startsWith('image/')) {
      return 'image';
    } else if (mimetype.startsWith('text/')) {
      return 'text';
    }
    return null;
  }
</script>

<div class="max-w-6xl mx-auto px-4 py-8">
  {#if loading}
    <div class="flex items-center justify-center py-16 text-muted">
      <div class="inline-block animate-spin">⏳</div>
      <p class="ml-3">Loading document...</p>
    </div>
  {:else if error}
    <Panel title="ERROR">
      <p class="text-danger mb-4">{error}</p>
      <Button onclick={() => goto('/')} tone="danger">
        ← Back to Dashboard
      </Button>
    </Panel>
  {:else if doc}
    <!-- Toolbar -->
    <div class="flex items-center justify-between mb-8">
      <Button onclick={() => goto('/')} variant="ghost">
        ← Back
      </Button>
      <div class="flex items-center gap-2">
        <Button onclick={handleDownload} variant="primary">
          Download
        </Button>
        {#if doc && (doc.is_owner || session.user?.role === 'admin')}
          <Button onclick={handleDelete} variant="danger">
            Delete
          </Button>
        {/if}
      </div>
    </div>

    <!-- Document Info Panel -->
    <Panel title={doc.title.toUpperCase()}>
      {#if updateError}
        <div class="mb-4 p-3 border border-danger text-danger text-sm">
          {updateError}
        </div>
      {/if}

      <!-- Owner and Category Info -->
      <div class="mb-6 space-y-3">
        <p class="text-muted text-sm">
          {#if doc.is_owner}
            Owned by you
          {:else}
            Uploaded by {doc.owner_username || 'Unknown'}
          {/if}
        </p>
        {#if doc.category}
          <div>
            <Badge text={doc.category} tone="cyan" />
          </div>
        {/if}
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
        <!-- Title -->
        <div>
          <div class="label mb-2">Title</div>
          {#if editingTitle && (doc.is_owner || session.user?.role === 'admin')}
            <div class="flex gap-2">
              <input
                type="text"
                bind:value={newTitle}
                disabled={updateLoading}
                class="input flex-1 text-sm disabled:opacity-50"
              />
              <Button
                onclick={handleUpdateTitle}
                disabled={updateLoading}
                variant="success"
              >
                ✓
              </Button>
              <Button
                onclick={() => {
                  editingTitle = false;
                  newTitle = doc.title;
                }}
                disabled={updateLoading}
                variant="ghost"
              >
                ✕
              </Button>
            </div>
          {:else}
            <div class="flex items-center justify-between">
              <p class="text-bright">{doc.title}</p>
              {#if doc.is_owner || session.user?.role === 'admin'}
                <Button
                  onclick={() => (editingTitle = true)}
                  variant="ghost"
                  size="sm"
                >
                  Edit
                </Button>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Category -->
        <div>
          <div class="label mb-2">Category</div>
          {#if editingCategory && (doc.is_owner || session.user?.role === 'admin')}
            <div class="flex gap-2">
              <input
                type="text"
                bind:value={newCategory}
                disabled={updateLoading}
                placeholder="e.g., Tax, Insurance"
                class="input flex-1 text-sm disabled:opacity-50"
              />
              <Button
                onclick={handleUpdateCategory}
                disabled={updateLoading}
                variant="success"
                size="sm"
              >
                ✓
              </Button>
              <Button
                onclick={() => {
                  editingCategory = false;
                  newCategory = doc.category || '';
                }}
                disabled={updateLoading}
                variant="ghost"
                size="sm"
              >
                ✕
              </Button>
            </div>
          {:else}
            <div class="flex items-center justify-between">
              <p class="text-bright">
                {#if doc.category}
                  {doc.category}
                {:else}
                  <span class="text-muted">Not set</span>
                {/if}
              </p>
              {#if doc.is_owner || session.user?.role === 'admin'}
                <Button
                  onclick={() => (editingCategory = true)}
                  variant="ghost"
                  size="sm"
                >
                  Edit
                </Button>
              {/if}
            </div>
          {/if}
        </div>

        <!-- File Info -->
        <div>
          <div class="label mb-2">Filename</div>
          <p class="text-bright font-mono break-all">{doc.blob.filename}</p>
        </div>

        <div>
          <div class="label mb-2">Size / Date</div>
          <p class="text-bright">
            {formatFileSize(doc.blob.size_bytes)} • {formatDate(doc.created_at)}
          </p>
        </div>
      </div>
    </Panel>

    <!-- Preview Panel -->
    <Panel title="VIEWPORT">
      <div class="border border-line hud-corners p-4 bg-panel-light">
        {#if getPreviewComponent() === 'pdf'}
          <iframe
            src={contentUrl(docId)}
            class="w-full h-96 border border-line"
            title="PDF Viewer"
          />
        {:else if getPreviewComponent() === 'image'}
          <img
            src={contentUrl(docId)}
            alt={doc.title}
            class="max-w-full h-auto max-h-96 mx-auto border border-line"
          />
        {:else if getPreviewComponent() === 'text'}
          <pre class="bg-ink p-4 overflow-auto max-h-96 text-xs text-bright font-mono border border-line">{contentText}</pre>
        {:else}
          <div class="text-center py-12 text-muted">
            <div class="text-6xl mb-4">📎</div>
            <p class="text-sm mb-4">No preview available for this file type</p>
            <p class="text-xs">{doc.blob.mimetype}</p>
            <Button
              onclick={handleDownload}
              variant="primary"
            >
              Download to view
            </Button>
          </div>
        {/if}
      </div>
    </Panel>
  {/if}
</div>
