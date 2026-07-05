<script lang="ts">
  // ctOS "hacker HUD" loader: a cyan segment sweeping a bracketed track plus a
  // monospace status label with blinking block glyphs. Matches the Watch_Dogs
  // aesthetic used across the app (see tailwind palette + keyframes).
  interface Props {
    label?: string;
  }
  const { label = 'PROCESSING' } = $props<Props>();
</script>

<div class="inline-flex flex-col items-center gap-2 font-mono select-none">
  <div class="flex items-center gap-1 text-cyan text-sm">
    <span>[</span>
    <div class="relative h-1.5 w-40 overflow-hidden bg-line">
      <div
        class="absolute top-0 h-full w-2/5 bg-cyan animate-scanx"
        style="box-shadow: 0 0 10px rgb(var(--c-cyan)), 0 0 4px rgb(var(--c-cyan));"
      ></div>
    </div>
    <span>]</span>
  </div>
  <div class="flex items-center gap-1 text-xs uppercase tracking-[0.3em] text-cyan animate-flicker">
    <span>{label}</span>
    <span class="text-muted">
      <span class="animate-pulse-dot">▓</span><span
        class="animate-pulse-dot"
        style="animation-delay: 0.15s;">▒</span><span
        class="animate-pulse-dot"
        style="animation-delay: 0.3s;">░</span>
    </span>
  </div>
</div>
