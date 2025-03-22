/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'processing': '#ff0000',
        'processing-dark': '#8b0000',
        'waiting': '#ffff00',
        'waiting-dark': '#b8860b',
        'done': '#00ff00',
        'done-dark': '#006400',
        'disabled': '#808080',
      },
    },
  },
  plugins: [],
}
