import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      '^/(api|poll|live|stats|reset-db|classify|investigate|investigation|score|flotte|classement|health|proxy-image|pays|vols|airport|osint|vip|pow|ecdh)([/?]|$)': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
