/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{svelte,ts,html}'],
  theme: {
    extend: {
      colors: {
        // Driven by CSS variables (see app.css) so the whole UI can switch
        // between the dark ctOS theme and a light theme.
        ink: 'rgb(var(--c-ink) / <alpha-value>)',
        panel: 'rgb(var(--c-panel) / <alpha-value>)',
        'panel-light': 'rgb(var(--c-panel-light) / <alpha-value>)',
        line: 'rgb(var(--c-line) / <alpha-value>)',
        cyan: 'rgb(var(--c-cyan) / <alpha-value>)',
        amber: 'rgb(var(--c-amber) / <alpha-value>)',
        danger: 'rgb(var(--c-danger) / <alpha-value>)',
        success: 'rgb(var(--c-success) / <alpha-value>)',
        muted: 'rgb(var(--c-muted) / <alpha-value>)',
        normal: 'rgb(var(--c-normal) / <alpha-value>)',
        bright: 'rgb(var(--c-bright) / <alpha-value>)'
      },
      fontFamily: {
        mono: ['"Cascadia Code"', '"JetBrains Mono"', 'ui-monospace', 'Consolas', 'monospace'],
        sans: ['"Cascadia Code"', '"JetBrains Mono"', 'ui-monospace', 'Consolas', 'monospace']
      },
      keyframes: {
        'pulse-dot': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.3' }
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' }
        },
        scanx: {
          '0%': { left: '-40%' },
          '100%': { left: '100%' }
        },
        flicker: {
          '0%, 19%, 21%, 23%, 25%, 54%, 56%, 100%': { opacity: '1' },
          '20%, 24%, 55%': { opacity: '0.8' }
        },
        glow: {
          '0%, 100%': { 'box-shadow': '0 0 10px rgba(34, 211, 238, 0.3)' },
          '50%': { 'box-shadow': '0 0 20px rgba(34, 211, 238, 0.6)' }
        }
      },
      animation: {
        'pulse-dot': 'pulse-dot 1.5s ease-in-out infinite',
        scan: 'scan 2s linear infinite',
        scanx: 'scanx 1.1s ease-in-out infinite',
        flicker: 'flicker 4s ease-in-out infinite',
        glow: 'glow 2s ease-in-out infinite'
      }
    }
  },
  plugins: [require('@tailwindcss/forms')],
  darkMode: 'class'
};
