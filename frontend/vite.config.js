import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'FlockGuard AI',
        short_name: 'FlockGuard',
        description: 'AI-native poultry intelligence and early-warning platform',
        theme_color: '#1B4332',
        background_color: '#F6F5F1',
        display: 'standalone',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
  build: {
    // Increase the chunk size warning limit to reduce noisy warnings during
    // Vercel builds and guide manual splitting for better cacheability.
    // Disable Vite's modulepreload polyfill to avoid "preloaded but not used"
    // console warnings when a service worker or cross-world scope intercepts
    // module requests.
    polyfillModulePreload: false,
    chunkSizeWarningLimit: 2000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react')) return 'vendor_react'
            if (id.includes('lodash')) return 'vendor_lodash'
            return 'vendor'
          }
        },
      },
    },
  },
})
