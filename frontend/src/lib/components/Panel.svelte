<script lang="ts">
  import StatusDot from './StatusDot.svelte';

  interface Props {
    title?: string;
    subtitle?: string;
    children?: unknown;
    right?: unknown;
  }

  const { title, subtitle, children, right } = $props<Props>();
</script>

<div class="hud-panel hud-corners">
  {#if title || right}
    <div class="flex items-center justify-between mb-3 pb-3 border-b border-line">
      <div>
        {#if title}
          <div class="flex items-center gap-2">
            <h2 class="text-sm uppercase font-bold tracking-widest text-bright glow-cyan">
              {title}
            </h2>
            {#if !subtitle}
              <StatusDot pulse={true} tone="cyan" />
            {/if}
          </div>
        {/if}
        {#if subtitle}
          <p class="text-xs text-muted uppercase tracking-wider mt-1">{subtitle}</p>
        {/if}
      </div>
      {#if right}
        <div>
          {@render right()}
        </div>
      {/if}
    </div>
  {/if}

  {#if children}
    <div>
      {@render children()}
    </div>
  {/if}
</div>

<style>
  :global(.hud-panel) {
    position: relative;
  }
</style>
