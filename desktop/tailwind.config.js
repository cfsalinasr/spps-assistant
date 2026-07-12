/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/renderer/index.html', './src/renderer/src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0f1117',
        bg2: '#161b25',
        bg3: '#1e2535',
        bg4: '#252d3e',
        teal: '#1fc9a0',
        amber: '#f0b429',
        red: '#e25c5c',
        text: '#e8eaf0',
        text2: '#8b92a8',
        text3: '#5a6178'
      },
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace']
      }
    }
  },
  plugins: []
}
