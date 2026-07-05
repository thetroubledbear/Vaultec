<script lang="ts">
  interface Props {
    label: string;
    value: string | number;
    accent?: 'cyan' | 'amber' | 'danger' | 'success';
    hint?: string;
  }

  const { label, value, accent = 'cyan', hint } = $props<Props>();

  const accentColor = {
    cyan: 'text-cyan',
    amber: 'text-amber',
    danger: 'text-danger',
    success: 'text-success'
  }[accent];
</script>

<div class="hud-panel">
  <div class="label mb-2">
    {label}
  </div>
  <div class="text-2xl font-bold {accentColor} tracking-wider mb-1 font-mono">
    {value}
  </div>
  {#if hint}
    <div class="text-xs text-muted font-mono">
      {hint}
    </div>
  {/if}
</div>
