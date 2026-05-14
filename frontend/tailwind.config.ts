import type { Config } from 'tailwindcss'
import typography from '@tailwindcss/typography'

export default {
  darkMode: 'class',
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      spacing: {
        '3xs': '2px',
        '2xs': '4px',
        'xs': '6px',
        'sm': '8px',
        'md': '12px',
        'lg': '16px',
        'xl': '20px',
        '2xl': '24px',
        '3xl': '32px'
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      colors: {
        background: '#0c0c10',
        foreground: '#fafafa',
        primary: '#e63946',
        'primary-foreground': '#ffffff',
        muted: 'rgba(255,255,255,0.08)',
        'muted-foreground': '#71717a',
        card: '#141418',
        'card-subtle': '#18181b',
        'glass-bg': 'rgba(255,255,255,0.03)',
        'glass-border': 'rgba(255,255,255,0.06)',
        'glass-border-hover': 'rgba(255,255,255,0.12)',
        'accent-red': '#e63946',
        'accent-green': '#22c55e',
        'accent-orange': '#f59e0b',
        'accent-blue': '#3b82f6',
        'accent-violet': '#7c3aed',
        'text-primary': '#fafafa',
        'text-muted': '#71717a',
        'text-subtle': '#52525b',
        border: 'rgba(255,255,255,0.06)',
        'border-subtle': 'rgba(255,255,255,0.06)',
        ghost: 'transparent',
        'ghost-foreground': '#71717a',  
        'ghost-hover': 'rgba(255,255,255,0.04)',
        outline: 'transparent',
        'outline-hover': 'rgba(255,255,255,0.04)',
        'surface-raised': 'rgba(255,255,255,0.03)',
        backdrop: 'rgba(0,0,0,0.5)',
      },
      boxShadow: {
        'card': '0 4px 24px rgba(0,0,0,0.4), 0 1px 0 rgba(255,255,255,0.04) inset',
        'card-hover': '0 8px 40px rgba(0,0,0,0.6)',
        'glow-red': '0 0 40px rgba(230,57,70,0.15)',
        'glow-green': '0 0 40px rgba(34,197,94,0.15)',
        'glow-blue': '0 0 40px rgba(59,130,246,0.15)',
      },
      backdropBlur: { xs: '4px' },
      animation: {
        'ping-slow': 'ping 2s cubic-bezier(0,0,0.2,1) infinite',
        'count-up': 'countUp 1s ease-out forwards',
        'slide-in': 'slideIn 0.3s ease-out forwards',
        'fade-up': 'fadeUp 0.4s ease-out forwards',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(-10px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [
    typography
  ],
} satisfies Config
