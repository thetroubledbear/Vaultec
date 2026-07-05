<script lang="ts">
  interface Props {
    text: string;
    tone?: 'cyan' | 'amber' | 'muted' | 'danger' | 'success';
  }

  const { text, tone = 'cyan' } = $props<Props>();

  const toneClass = {
    cyan: 'badge-cyan',
    amber: 'badge-amber',
    muted: 'badge-muted',
    danger: 'badge-danger',
    success: 'badge-success'
  }[tone];
</script>

<span class="badge {toneClass}">
  {text}
</span>
