<script lang="ts">
  interface DataPoint {
    label: string;
    value: number;
  }

  interface Props {
    data: DataPoint[];
    accent?: 'cyan' | 'amber' | 'danger' | 'success';
  }

  const { data, accent = 'cyan' } = $props<Props>();

  const maxValue = $derived(data.length > 0 ? Math.max(...data.map((d) => d.value)) : 1);

  const accentClass = {
    cyan: 'bg-cyan',
    amber: 'bg-amber',
    danger: 'bg-danger',
    success: 'bg-success'
  }[accent];
</script>

{#if data.length === 0}
  <div class="text-muted text-sm">No data available</div>
{:else}
  <div class="space-y-2.5 font-mono">
    {#each data as item}
      <div class="flex items-center gap-3 text-xs">
        <span class="w-28 shrink-0 truncate text-normal uppercase tracking-wide" title={item.label}>
          {item.label}
        </span>
        <div class="flex-1 h-4 bg-panel-light border border-line overflow-hidden">
          <div
            class="h-full {accentClass} transition-all duration-300"
            style="width: {maxValue > 0 ? (item.value / maxValue) * 100 : 0}%"
          ></div>
        </div>
        <span class="w-8 shrink-0 text-right text-cyan tabular-nums">{item.value}</span>
      </div>
    {/each}
  </div>
{/if}
