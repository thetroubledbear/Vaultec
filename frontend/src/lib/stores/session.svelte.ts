import { apiJson } from '$lib/api';

export interface User {
  id: string;
  username: string;
  role: string;
}

export interface Health {
  status: string;
  initialized: boolean;
  unlocked: boolean;
}

interface SessionState {
  health: Health | null;
  user: User | null;
  loading: boolean;
  error: string | null;
}

function createSessionStore() {
  let state = $state<SessionState>({
    health: null,
    user: null,
    loading: false,
    error: null
  });

  return {
    get health() {
      return state.health;
    },
    get user() {
      return state.user;
    },
    get loading() {
      return state.loading;
    },
    get error() {
      return state.error;
    },
    get initialized() {
      return state.health?.initialized ?? false;
    },
    get unlocked() {
      return state.health?.unlocked ?? false;
    },
    get isAuthenticated() {
      return state.user !== null;
    },

    async refresh() {
      state.loading = true;
      state.error = null;

      try {
        const health = await apiJson<Health>('/health');
        state.health = health;

        if (health.initialized) {
          try {
            const user = await apiJson<User>('/api/auth/me');
            state.user = user;
          } catch {
            state.user = null;
          }
        }
      } catch (err) {
        state.error = err instanceof Error ? err.message : 'Failed to load session';
      } finally {
        state.loading = false;
      }
    },

    setUser(user: User | null) {
      state.user = user;
    },

    setHealth(health: Health) {
      state.health = health;
    },

    clearError() {
      state.error = null;
    }
  };
}

export const session = createSessionStore();
