import { apiJson } from '$lib/api';

interface ValidationCount {
  pending: number;
}

function createValidationStore() {
  let pendingCount = $state(0);
  let loading = $state(false);

  return {
    get pending() {
      return pendingCount;
    },
    get loading() {
      return loading;
    },

    async refresh() {
      loading = true;
      try {
        const data = await apiJson<ValidationCount>('/api/validation/count');
        pendingCount = data.pending;
      } catch (err) {
        console.error('Failed to fetch validation count:', err);
      } finally {
        loading = false;
      }
    },

    setPending(count: number) {
      pendingCount = count;
    }
  };
}

export const validation = createValidationStore();
