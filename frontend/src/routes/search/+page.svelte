<script lang="ts">
  import { session } from '$lib/stores/session.svelte.ts';
  import { apiJson, ApiError } from '$lib/api';
  import Panel from '$lib/components/Panel.svelte';
  import Button from '$lib/components/Button.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import Loader from '$lib/components/Loader.svelte';

  interface AiStatus {
    embed_provider: string;
    embed_model: string;
    chat_provider: string;
    chat_model: string;
    anthropic_key_set: boolean;
    openai_key_set: boolean;
    active_docs: number;
    docs_with_extraction: number;
    docs_with_embeddings: number;
    pending_docs: number;
  }

  interface SearchResult {
    document_id: string;
    title: string;
    snippet: string;
    score: number;
    match: 'keyword' | 'semantic' | 'both';
  }

  interface SearchResponse {
    results: SearchResult[];
  }

  interface AskResponse {
    answer: string;
    sources: Array<{
      document_id: string;
      title: string;
      snippet: string;
    }>;
  }

  let status = $state<AiStatus | null>(null);
  let query = $state('');
  let searchResults = $state<SearchResult[]>([]);
  let searchLoading = $state(false);
  let searchError = $state('');

  let question = $state('');
  let answer = $state('');
  let sources = $state<Array<{ document_id: string; title: string; snippet: string }>>([]);
  let askLoading = $state(false);
  let askError = $state('');

  let statusError = $state('');

  async function loadStatus() {
    try {
      statusError = '';
      status = await apiJson<AiStatus>('/api/ai/status');
    } catch (err) {
      console.error('Failed to load AI status:', err);
      statusError = err instanceof Error ? err.message : 'Failed to load status';
    }
  }

  async function handleSearch() {
    if (!query.trim()) {
      searchResults = [];
      searchError = '';
      return;
    }

    try {
      searchLoading = true;
      searchError = '';
      const response = await apiJson<SearchResponse>(
        `/api/ai/search?q=${encodeURIComponent(query)}&limit=10`
      );
      searchResults = response.results;
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 503) {
          searchError = 'AI is not available right now (provider offline).';
        } else if (err.status === 423) {
          searchError = 'Vault is locked.';
        } else {
          searchError = err.detail;
        }
      } else {
        searchError = err instanceof Error ? err.message : 'Search failed';
      }
    } finally {
      searchLoading = false;
    }
  }

  async function handleAsk() {
    if (!question.trim()) {
      askError = 'Please enter a question';
      return;
    }

    try {
      askLoading = true;
      askError = '';
      answer = '';
      sources = [];

      const response = await apiJson<AskResponse>('/api/ai/ask', 'POST', {
        question: question.trim()
      });

      answer = response.answer;
      sources = response.sources || [];
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 503) {
          askError = 'AI is not available right now (provider offline).';
        } else if (err.status === 423) {
          askError = 'Vault is locked.';
        } else {
          askError = err.detail;
        }
      } else {
        askError = err instanceof Error ? err.message : 'Failed to get answer';
      }
      answer = '';
      sources = [];
    } finally {
      askLoading = false;
    }
  }

  $effect.pre(async () => {
    if (session.isAuthenticated && session.unlocked) {
      await loadStatus();
    }
  });

  function getMatchBadgeTone(match: string): string {
    if (match === 'both') return 'success';
    if (match === 'semantic') return 'cyan';
    return 'normal';
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
      <h1 class="text-2xl uppercase font-bold tracking-widest text-bright glow-cyan">// SEARCH & ASK</h1>
    </div>

    <!-- Status Strip -->
    {#if status}
      <div class="mb-8 p-4 border border-line bg-panel rounded-lg">
        <div class="flex flex-col gap-2">
          <div class="text-xs uppercase tracking-wider">
            <span class="text-bright">Indexing:</span>
            <span class="text-muted">
              {status.docs_with_extraction} of {status.active_docs} documents indexed
            </span>
            {#if status.pending_docs > 0}
              <span class="text-amber-600 dark:text-amber-400 ml-3">
                ({status.pending_docs} still processing...)
              </span>
            {/if}
          </div>
          <div class="text-xs uppercase tracking-wider text-muted">
            <span class="text-bright">Providers:</span>
            {status.embed_provider || 'none'} (embed) â€¢ {status.chat_provider || 'none'} (chat)
          </div>
        </div>
      </div>
    {/if}

    <!-- Search Section -->
    <Panel title="SEARCH DOCUMENTS">
      <div class="space-y-4">
        <div class="flex gap-2">
          <input
            type="text"
            bind:value={query}
            placeholder="Enter search query..."
            class="input flex-1 text-sm"
            disabled={searchLoading}
          />
          <Button onclick={handleSearch} disabled={searchLoading} variant="primary">
            {searchLoading ? '[ SEARCHING... ]' : '[ SEARCH ]'}
          </Button>
        </div>

        {#if searchError}
          <div class="p-3 border border-danger text-danger text-sm">
            {searchError}
          </div>
        {/if}

        {#if searchLoading}
          <div class="text-center py-8">
            <Loader label="Scanning" />
          </div>
        {:else if query.trim() && searchResults.length === 0}
          <div class="text-center py-8">
            <div class="text-4xl mb-2">ðŸ”</div>
            <p class="text-muted text-sm">No matches found</p>
          </div>
        {:else if searchResults.length > 0}
          <div class="space-y-3">
            {#each searchResults as result (result.document_id)}
              <div class="border border-line bg-panel-light rounded-lg p-4 hover:border-cyan transition-colors">
                <div class="flex items-start justify-between gap-4 mb-2">
                  <h3 class="font-bold text-bright text-sm uppercase flex-1">
                    {result.title}
                  </h3>
                  <Badge text={result.match.toUpperCase()} tone={getMatchBadgeTone(result.match)} />
                </div>
                <div class="text-xs text-muted mb-3 font-mono">
                  Match score: {(result.score * 100).toFixed(0)}%
                </div>
                <div class="text-xs text-muted mb-3 leading-relaxed">
                  {@html result.snippet}
                </div>
                <a
                  href={`/api/documents/${result.document_id}/content`}
                  target="_blank"
                  rel="noreferrer"
                  class="text-cyan hover:text-cyan text-xs uppercase tracking-wider hover:underline"
                >
                  â†’ Open Document
                </a>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </Panel>

    <!-- Ask Section -->
    <div class="mt-8">
      <Panel title="ASK A QUESTION">
        <div class="space-y-4">
          <div class="flex flex-col gap-2">
            <textarea
              bind:value={question}
              placeholder="Ask a question about your documents..."
              class="input flex-1 text-sm resize-none"
              rows="4"
              disabled={askLoading}
            />
            <Button onclick={handleAsk} disabled={askLoading} variant="primary">
              {askLoading ? '[ THINKING... ]' : '[ ASK ]'}
            </Button>
          </div>

          {#if askError}
            <div class="p-3 border border-danger text-danger text-sm">
              {askError}
            </div>
          {/if}

          {#if askLoading}
            <div class="text-center py-8">
              <Loader label="Analyzing" />
            </div>
          {/if}

          {#if answer}
            <div class="space-y-4">
              <!-- Answer -->
              <div class="p-4 border-2 border-cyan bg-cyan/5 dark:bg-cyan/10 rounded-lg">
                <div class="text-xs uppercase tracking-wider text-bright mb-2">ANSWER</div>
                <div class="text-sm text-bright leading-relaxed whitespace-pre-wrap">
                  {answer}
                </div>
              </div>

              <!-- Sources -->
              {#if sources.length > 0}
                <div>
                  <div class="text-xs uppercase tracking-wider text-bright mb-3">SOURCES</div>
                  <div class="space-y-2">
                    {#each sources as source, idx (source.document_id)}
                      <div class="border border-line bg-panel-light rounded-lg p-3">
                        <div class="flex items-start justify-between gap-2 mb-2">
                          <div>
                            <div class="font-bold text-bright text-xs uppercase">
                              [{idx + 1}] {source.title}
                            </div>
                          </div>
                        </div>
                        <div class="text-xs text-muted mb-2 leading-relaxed">
                          {@html source.snippet}
                        </div>
                        <a
                          href={`/api/documents/${source.document_id}/content`}
                          target="_blank"
                          rel="noreferrer"
                          class="text-cyan hover:text-cyan text-xs uppercase tracking-wider hover:underline"
                        >
                          â†’ View Document
                        </a>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      </Panel>
    </div>
  {/if}
</div>
