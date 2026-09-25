/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#ffffff',
          muted: '#f6f7f9',
          sunken: '#eef0f3',
        },
        ink: {
          DEFAULT: '#1a1d23',
          muted: '#5a6270',
          faint: '#8a919e',
        },
        line: '#e2e5ea',
        brand: {
          DEFAULT: '#2454a6',
          light: '#e8eefb',
        },
        urgent: {
          red: '#c8402f',
          redBg: '#fbeae7',
          yellow: '#b8791a',
          yellowBg: '#fbf1de',
        },
        ki: {
          strong: '#166a4d',
          strongBg: '#e2f4ea',
          possible: '#7a6a1f',
          possibleBg: '#f6f0d9',
          none: '#8a919e',
          noneBg: '#f0f1f3',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 1px 2px rgba(20, 24, 32, 0.06), 0 1px 1px rgba(20, 24, 32, 0.04)',
      },
    },
  },
  plugins: [],
}
