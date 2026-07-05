<script lang="ts">
  import { goto } from '$app/navigation';
  import { session } from '$lib/stores/session.svelte.ts';
  import { apiJson, apiMultipart, apiDownload, ApiError } from '$lib/api';
  import { formatFileSize, formatDate } from '$lib/utils';
  import Panel from '$lib/components/Panel.svelte';
  import StatCard from '$lib/components/StatCard.svelte';
  import Button from '$lib/components/Button.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import ProgressBar from '$lib/components/ProgressBar.svelte';
  import BarChart from '$lib/components/BarChart.svelte';
  import Donut from '$lib/components/Donut.svelte';

  interface Document {
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

  interface Category {
    id: string;
    name: string;
    document_count: number;
  }

  let documents = $state<Document[]>([]);
  let allDocuments = $state<Document[]>([]);
  let categories = $state<Category[]>([]);
  let loading = $state(false);
  let uploading = $state(false);
  let uploadProgress = $state('');
  let error = $state('');
  let successMessage = $state('');

  let fileInput: HTMLInputElement;
  let uploadTitle = $state('');
  let uploadCategory = $state('');

  async function loadDocuments() {
    try {
      loading = true;
      error = '';
      const response = await apiJson<{ documents: Document[] }>('/api/documents/');
      allDocuments = response.documents;
      filterDocuments();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load documents';
    } finally {
      loading = false;
    }
  }

  async function loadCategories() {
    try {
      categories = await apiJson<Category[]>('/api/documents/categories');
    } catch (err) {
      console.error('Failed to load categories:', err);
    }
  }

  function filterDocuments() {
    let filtered = allDocuments;

    if (selectedCategory !== 'all') {
      filtered = filtered.filter(d => d.category === selectedCategory);
    }

    documents = filtered;
  }

  async function handleSearch() {
    if (!searchQuery.trim()) {
      allDocuments = [];
      documents = [];
      return;
    }

    try {
      searchLoading = true;
      error = '';
      const response = await apiJson<{ documents: Document[] }>(
        `/api/documents/?q=${encodeURIComponent(searchQuery)}`
      );
      allDocuments = response.documents;
      filterDocuments();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Search failed';
    } finally {
      searchLoading = false;
    }
  }

  // Refresh live vault/health state on mount so a stale cached "locked" status
  // (e.g. the api restarted after the page first loaded) self-corrects and docs load.
  $effect(() => {
    session.refresh();
  });

  $effect.pre(() => {
    if (session.isAuthenticated && session.unlocked) {
      loadDocuments();
      loadCategories();
    }
  });

  $effect(() => {
    filterDocuments();
  });

  async function handleUpload() {
    error = '';
    successMessage = '';

    if (!fileInput.files?.length) {
      error = 'Please select a file';
      return;
    }

    if (!uploadTitle.trim()) {
      error = 'Please enter a title';
      return;
    }

    try {
      uploading = true;
      uploadProgress = 'READING';
      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      formData.append('title', uploadTitle.trim());
      if (uploadCategory.trim()) {
        formData.append('category', uploadCategory.trim());
      }

      // Cycle upload progress stages
      const stages = ['READING', 'ENCRYPTING', 'STORING'];
      const progressInterval = setInterval(() => {
        const currentIndex = stages.indexOf(uploadProgress);
        uploadProgress = stages[(currentIndex + 1) % stages.length];
      }, 600);

      await apiMultipart('/api/documents/', formData);
      clearInterval(progressInterval);
      uploadProgress = '';
      successMessage = 'Document uploaded successfully!';
      uploadTitle = '';
      uploadCategory = '';
      fileInput.value = '';

      setTimeout(() => {
        successMessage = '';
        loadDocuments();
      }, 2000);
    } catch (err) {
      if (err instanceof ApiError && err.status === 423) {
        error = 'Vault is locked. Please unlock first.';
      } else {
        error = err instanceof Error ? err.message : 'Upload failed';
      }
    } finally {
      uploading = false;
      uploadProgress = '';
    }
  }

  function calculateStorageUsed(): number {
    return allDocuments.reduce((total, doc) => total + (doc.blob.size_bytes || 0), 0);
  }

  function calculateYourUploads(): number {
    return allDocuments.filter(doc => doc.is_owner).length;
  }

  function getCategoriesForChart() {
    const catMap: Record<string, number> = {};
    allDocuments.forEach(doc => {
      const cat = doc.category || 'Uncategorized';
      catMap[cat] = (catMap[cat] || 0) + 1;
    });
    return Object.entries(catMap).map(([name, count]) => ({ label: name, value: count }));
  }

  function getOwnersForChart() {
    const ownerMap: Record<string, number> = {};
    allDocuments.forEach(doc => {
      const owner = doc.is_owner ? 'You' : (doc.owner_username || 'Unknown');
      ownerMap[owner] = (ownerMap[owner] || 0) + 1;
    });
    return Object.entries(ownerMap).map(([name, count]) => ({ label: name, value: count }));
  }

  let searchQuery = $state('');
  let selectedCategory = $state('all');
  let viewMode = $state<'grid' | 'list'>('grid');
  let searchLoading = $state(false);

  async function downloadDocument(docId: string, filename: string) {
    try {
      const blob = await apiDownload(`/api/documents/${docId}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Download failed');
    }
  }

  async function deleteDocument(docId: string) {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await apiJson(`/api/documents/${docId}`, 'DELETE');
      await loadDocuments();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    }
  }

  function getFileIcon(mimetype: string | null | undefined): string {
    if (!mimetype) return 'ðŸ“Ž';
    if (mimetype.startsWith('image/')) return 'ðŸ–¼';
    if (mimetype === 'application/pdf') return 'ðŸ“„';
    if (mimetype.startsWith('text/')) return 'ðŸ“';
    return 'ðŸ“Ž';
  }
</script>

<div class="max-w-7xl mx-auto px-4 py-8">
  {#if !session.unlocked}
    <div class="mb-8 p-6 bg-amber-50 dark:bg-amber-900/20 border-2 border-amber-200 dark:border-amber-800 rounded-lg">
      <h2 class="text-lg font-semibold text-amber-900 dark:text-amber-200 mb-2">ðŸ”’ Vault is Locked</h2>
      <p class="text-amber-800 dark:text-amber-300 mb-4">
        Your vault has been locked. Use the Unlock button in the top bar to unlock it with your master passphrase.
      </p>
    </div>
  {:else}
    <!-- Header -->
    <div class="mb-8 flex items-center gap-3">
      <h1 class="text-2xl uppercase font-bold tracking-widest text-bright glow-cyan">// VAULT</h1>
    </div>

    <!-- Analytics Strip (only when unlocked and docs exist) -->
    {#if allDocuments.length > 0}
      <div class="mb-8 space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Documents" value={allDocuments.length} accent="cyan" />
          <StatCard label="Categories" value={categories.length} accent="cyan" />
          <StatCard
            label="Storage Used"
            value={formatFileSize(calculateStorageUsed())}
            accent="cyan"
          />
          <StatCard label="Your Uploads" value={calculateYourUploads()} accent="cyan" />
        </div>
        {#if getCategoriesForChart().length > 0}
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Panel title="DOCUMENTS BY CATEGORY">
              <BarChart data={getCategoriesForChart()} accent="cyan" />
            </Panel>
            <Panel title="DOCUMENTS BY OWNER">
              <Donut segments={getOwnersForChart()} />
            </Panel>
          </div>
        {/if}
      </div>
    {/if}

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Upload Section -->
      <div class="lg:col-span-1">
        <Panel title="UPLOAD">
          <div class="space-y-4">
            {#if successMessage}
              <div class="p-3 border border-success text-success text-sm">
                [ OK ] {successMessage}
              </div>
            {/if}

            {#if error}
              <div class="p-3 border border-danger text-danger text-sm">
                {error}
              </div>
            {/if}

            <div>
              <div class="label mb-2">File</div>
              <input
                bind:this={fileInput}
                type="file"
                disabled={uploading}
                class="input w-full text-sm disabled:opacity-50"
              />
            </div>

            <div>
              <div class="label mb-2">Title *</div>
              <input
                type="text"
                bind:value={uploadTitle}
                disabled={uploading}
                placeholder="Document title"
                class="input w-full text-sm disabled:opacity-50"
              />
            </div>

            <div>
              <div class="label mb-2">Category (optional)</div>
              <input
                type="text"
                bind:value={uploadCategory}
                disabled={uploading}
                placeholder="e.g., Tax, Insurance"
                class="input w-full text-sm disabled:opacity-50"
              />
            </div>

            <!-- Upload Progress Indicator -->
            {#if uploading && uploadProgress}
              <div>
                <ProgressBar indeterminate={true} label={uploadProgress} />
              </div>
            {/if}

            <Button onclick={handleUpload} disabled={uploading} variant="primary">
              {uploading ? `[ ${uploadProgress} ]` : '[ UPLOAD ]'}
            </Button>
          </div>
        </Panel>
      </div>

      <!-- Documents Section -->
      <div class="lg:col-span-2">
        <Panel title="DOCUMENTS">
          <!-- Search and Controls -->
          <div class="space-y-4 mb-4">
            <input
              type="text"
              bind:value={searchQuery}
              onchange={handleSearch}
              placeholder="Search documents..."
              class="input w-full text-sm"
            />

            <!-- View Mode Toggle -->
            <div class="flex gap-2">
              <Button
                onclick={() => (viewMode = 'grid')}
                variant={viewMode === 'grid' ? 'primary' : 'ghost'}
              >
                âŠž Grid
              </Button>
              <Button
                onclick={() => (viewMode = 'list')}
                variant={viewMode === 'list' ? 'primary' : 'ghost'}
              >
                â‰¡ List
              </Button>
            </div>

            <!-- Category Filter -->
            {#if categories.length > 0}
              <div class="flex flex-wrap gap-2">
                <Button
                  onclick={() => (selectedCategory = 'all')}
                  variant={selectedCategory === 'all' ? 'primary' : 'ghost'}
                >
                  All
                </Button>
                {#each categories as cat (cat.id)}
                  <Button
                    onclick={() => (selectedCategory = cat.name)}
                    variant={selectedCategory === cat.name ? 'primary' : 'ghost'}
                  >
                    {cat.name}
                  </Button>
                {/each}
              </div>
            {/if}
          </div>

          <!-- Documents Display -->
          {#if loading || searchLoading}
            <div class="text-center text-muted">
              <div class="inline-block animate-spin">â³</div>
              <p class="mt-2">Loading documents...</p>
            </div>
          {:else if searchQuery.trim() && documents.length === 0}
            <div class="text-center">
              <div class="text-4xl mb-2">ðŸ”</div>
              <p class="text-muted">No documents found matching your search.</p>
            </div>
          {:else if documents.length === 0}
            <div class="text-center">
              <div class="text-4xl mb-2">ðŸ“„</div>
              <p class="text-muted">No documents yet. Upload one to get started!</p>
            </div>
          {:else if viewMode === 'grid'}
            <!-- Grid View -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {#each documents as doc (doc.id)}
                <div class="hud-panel hud-corners">
                  <!-- File Preview -->
                  <div class="mb-3 bg-panel-light border border-line rounded h-32 flex items-center justify-center overflow-hidden">
                    {#if doc.blob?.mimetype?.startsWith('image/')}
                      <img
                        src={`/api/documents/${doc.id}/content`}
                        alt={doc.title}
                        class="w-full h-full object-cover"
                      />
                    {:else if doc.blob?.mimetype === 'application/pdf'}
                      <iframe
                        src={`/api/documents/${doc.id}/content#toolbar=0&navpanes=0&view=FitH`}
                        title={doc.title}
                        loading="lazy"
                        class="w-full h-full pointer-events-none border-0"
                      ></iframe>
                    {:else}
                      <div class="text-4xl">{getFileIcon(doc.blob?.mimetype)}</div>
                    {/if}
                  </div>

                  <!-- Info -->
                  <h3 class="font-bold text-bright mb-1 line-clamp-2 text-sm uppercase">
                    {doc.title}
                  </h3>
                  <!-- Owner -->
                  <p class="text-xs text-muted mb-2">
                    Uploaded by {doc.is_owner ? 'You' : (doc.owner_username || 'Unknown')}
                  </p>
                  {#if doc.category}
                    <div class="mb-2">
                      <Badge text={doc.category} tone="cyan" />
                    </div>
                  {/if}
                  <p class="text-xs text-muted mb-3 font-mono">
                    {formatFileSize(doc.blob.size_bytes)} â€¢ {formatDate(doc.created_at)}
                  </p>

                  <!-- Actions -->
                  <div class="flex flex-wrap gap-2">
                    <Button onclick={() => goto(`/document/${doc.id}`)} variant="primary">
                      View
                    </Button>
                    <Button
                      onclick={() => downloadDocument(doc.id, doc.blob.filename)}
                      variant="ghost"
                    >
                      Download
                    </Button>
                    {#if doc.is_owner || session.user?.role === 'admin'}
                      <Button
                        onclick={() => deleteDocument(doc.id)}
                        variant="danger"
                      >
                        Delete
                      </Button>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {:else}
            <!-- List View -->
            <div class="overflow-x-auto">
              <table class="w-full text-xs font-mono">
                <thead>
                  <tr class="border-b border-line">
                    <th class="px-4 py-2 text-left label">Title</th>
                    <th class="px-4 py-2 text-left label">Owner</th>
                    <th class="px-4 py-2 text-left label">Category</th>
                    <th class="px-4 py-2 text-left label">Size</th>
                    <th class="px-4 py-2 text-left label">Date</th>
                    <th class="px-4 py-2 text-right label">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {#each documents as doc (doc.id)}
                    <tr class="border-b border-line hover:bg-panel-light transition">
                      <td class="px-4 py-3 text-bright truncate">
                        {doc.title}
                      </td>
                      <td class="px-4 py-3 text-muted">
                        {doc.is_owner ? 'You' : (doc.owner_username || 'Unknown')}
                      </td>
                      <td class="px-4 py-3 text-muted">
                        {doc.category || '-'}
                      </td>
                      <td class="px-4 py-3 text-muted">
                        {formatFileSize(doc.blob.size_bytes)}
                      </td>
                      <td class="px-4 py-3 text-muted">
                        {formatDate(doc.created_at)}
                      </td>
                      <td class="px-4 py-3 text-right">
                        <div class="flex items-center justify-end gap-1">
                          <Button
                            onclick={() => goto(`/document/${doc.id}`)}
                            variant="primary"
                          >
                            View
                          </Button>
                          <Button
                            onclick={() => downloadDocument(doc.id, doc.blob.filename)}
                            variant="ghost"
                          >
                            Download
                          </Button>
                          {#if doc.is_owner || session.user?.role === 'admin'}
                            <Button
                              onclick={() => deleteDocument(doc.id)}
                              variant="danger"
                            >
                              Delete
                            </Button>
                          {/if}
                        </div>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </Panel>
      </div>
    </div>
  {/if}
</div>
