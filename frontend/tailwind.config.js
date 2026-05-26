/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#fff7ed',
        paper: '#050505',
        teal: '#7bdff2',
        coral: '#ff6b35',
        grape: '#6f8cff',
        amber: '#ffb238'
      },
      boxShadow: {
        soft: '0 24px 80px rgba(0, 0, 0, 0.34)'
      }
    }
  },
  plugins: []
};
