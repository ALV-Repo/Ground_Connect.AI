export default {
  darkMode: 'class',
  content: ['./index.html','./src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: { 50:'#eef2ff',100:'#e0e7ff',200:'#c7d2fe',300:'#a5b4fc',400:'#818cf8',500:'#6366f1',600:'#4f46e5',700:'#4338ca',800:'#3730a3',900:'#312e81',950:'#1e1b4b' },
      },
      fontFamily: { sans: ['Inter','system-ui','sans-serif'] },
      boxShadow: { card:'0 1px 3px rgba(0,0,0,0.04),0 4px 12px rgba(0,0,0,0.04)', float:'0 8px 32px rgba(0,0,0,0.12),0 2px 8px rgba(0,0,0,0.06)', glow:'0 0 20px -5px rgba(99,102,241,0.5)' },
      animation: { 'fade-in':'fadeIn 0.25s ease', 'slide-up':'slideUp 0.28s ease' },
      keyframes: { fadeIn:{from:{opacity:0},to:{opacity:1}}, slideUp:{from:{opacity:0,transform:'translateY(10px)'},to:{opacity:1,transform:'translateY(0)'}} }
    }
  },
  plugins: []
}
