<script lang="ts">
  interface Props {
    variant?: 'primary' | 'danger' | 'ghost' | 'success';
    disabled?: boolean;
    loading?: boolean;
    type?: 'button' | 'submit' | 'reset';
    onclick?: (e: MouseEvent) => void;
    children?: unknown;
  }

  const {
    variant = 'primary',
    disabled = false,
    loading = false,
    type = 'button',
    onclick,
    children
  } = $props<Props>();

  // $derived so the class updates when the `variant` prop changes (e.g. grid/list toggle).
  const variantClass = $derived({
    primary: 'btn-primary',
    danger: 'btn-danger',
    ghost: 'btn-ghost',
    success: 'btn-success'
  }[variant]);
</script>

<button
  {type}
  disabled={disabled || loading}
  onclick={onclick}
  class="btn {variantClass}"
>
  {#if loading}
    <span class="inline-block mr-2 animate-pulse-dot font-mono" aria-hidden="true">▮</span>
  {/if}
  {#if children}
    {@render children()}
  {/if}
</button>
