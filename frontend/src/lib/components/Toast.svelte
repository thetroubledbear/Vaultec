<script lang="ts">
  interface Props {
    message: string;
    type?: 'success' | 'error' | 'info';
  }

  let { message, type = 'info' }: Props = $props();

  const bgClass = {
    success: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-200',
    error: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-200',
    info: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-200'
  };
</script>

<div class="p-3 {bgClass[type]} border rounded-lg text-sm">
  {message}
</div>
