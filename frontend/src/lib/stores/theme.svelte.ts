type Theme = 'dark' | 'light';

const STORAGE_KEY = 'vaultec-theme';

function createThemeStore() {
  let current = $state<Theme>('dark');

  function apply() {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', current);
    }
  }

  return {
    get value() {
      return current;
    },
    init() {
      if (typeof localStorage !== 'undefined') {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved === 'light' || saved === 'dark') {
          current = saved;
        }
      }
      apply();
    },
    toggle() {
      current = current === 'dark' ? 'light' : 'dark';
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, current);
      }
      apply();
    }
  };
}

export const theme = createThemeStore();
