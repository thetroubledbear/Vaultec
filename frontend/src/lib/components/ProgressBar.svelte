<script lang="ts">
  interface Props {
    value?: number;
    indeterminate?: boolean;
    label?: string;
  }

  const { value = 0, indeterminate = false, label } = $props<Props>();

  const clampedValue = Math.min(Math.max(value, 0), 100);
</script>

<div>
  {#if label}
    <div class="label mb-2">{label}</div>
  {/if}
  <div class="relative w-full h-3 bg-panel-light border border-line overflow-hidden">
    {#if indeterminate}
      <div class="absolute inset-0 bg-gradient-to-r from-transparent via-cyan to-transparent animate-scan" />
    {:else}
      <div
        class="h-full bg-cyan transition-all duration-300"
        style="width: {clampedValue}%;"
      />
    {/if}
  </div>
  {#if !indeterminate}
    <div class="text-xs text-muted text-right mt-1">{clampedValue}%</div>
  {/if}
</div>
