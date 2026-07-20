import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss(), react()],
  base: process.env.VITE_BASE || '/news_analyze/',  // GitHub Pages 用預設;docker build 設 VITE_BASE=/
})
