<script lang="ts">
  interface Segment {
    label: string;
    value: number;
    color?: string;
  }

  interface Props {
    segments: Segment[];
  }

  const { segments } = $props<Props>();

  const defaultColors = ['#22d3ee', '#f59e0b', '#ef4444', '#22c55e', '#8ba3b8'];

  const total = $derived(segments.reduce((sum, s) => sum + s.value, 0));

  // Use a plain local accumulator INSIDE the derived computation. Do NOT use a
  // $state here: a $derived that both reads and writes a $state loops forever.
  const pathData = $derived.by(() => {
    let cumulativeAngle = 0;
    return segments.map((segment, i) => {
    const percentage = total > 0 ? (segment.value / total) * 100 : 0;
    const angle = (percentage / 100) * 360;
    const startAngle = cumulativeAngle;
    const endAngle = startAngle + angle;

    cumulativeAngle = endAngle;

    const radius = 50;
    const innerRadius = 30;

    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;

    const x1 = 60 + radius * Math.cos(startRad);
    const y1 = 60 + radius * Math.sin(startRad);
    const x2 = 60 + radius * Math.cos(endRad);
    const y2 = 60 + radius * Math.sin(endRad);

    const ix1 = 60 + innerRadius * Math.cos(startRad);
    const iy1 = 60 + innerRadius * Math.sin(startRad);
    const ix2 = 60 + innerRadius * Math.cos(endRad);
    const iy2 = 60 + innerRadius * Math.sin(endRad);

    const largeArc = angle > 180 ? 1 : 0;

    const path = `
      M ${x1} ${y1}
      A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}
      L ${ix2} ${iy2}
      A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${ix1} ${iy1}
      Z
    `;

    return {
      path,
      color: segment.color || defaultColors[i % defaultColors.length],
      segment,
      percentage
    };
    });
  });
</script>

{#if segments.length === 0}
  <div class="text-muted text-sm">No data available</div>
{:else}
  <div class="flex items-center gap-6 font-mono">
    <!-- Donut chart -->
    <svg width="130" height="130" viewBox="0 0 120 120" class="flex-shrink-0">
      {#each pathData as item}
        <path d={item.path} fill={item.color} stroke-width="1" style="stroke: rgb(var(--c-ink))" />
      {/each}
    </svg>

    <!-- Legend -->
    <div class="flex-1 min-w-0 space-y-2.5">
      {#each pathData as item}
        <div class="flex items-center gap-2.5 text-xs">
          <span
            class="w-3 h-3 shrink-0 rounded-sm"
            style="background-color: {item.color};"
          ></span>
          <span class="text-normal truncate uppercase tracking-wide" title={item.segment.label}>
            {item.segment.label}
          </span>
          <span class="text-muted ml-auto shrink-0 tabular-nums pl-2">{item.percentage.toFixed(1)}%</span>
        </div>
      {/each}
    </div>
  </div>
{/if}
