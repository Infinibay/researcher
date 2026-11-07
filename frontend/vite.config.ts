/** Compile the workspace with React and Tailwind; keep browser and local API targets explicit. @module */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync } from 'node:fs'

export default defineConfig({
  plugins: [react(), tailwindcss(), {
    name: 'researcher-project-license',
    apply: 'build',
    /** Include the unchanged project license alongside every distributable web build. */
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'assets/PROJECT_LICENSE.txt',
        source: readFileSync(new URL('../LICENSE.md', import.meta.url), 'utf8') })
    },
  }],
  build: {
    target: ['chrome111', 'edge111', 'firefox128', 'safari16.4'],
    license: { fileName: 'assets/THIRD_PARTY_LICENSES.md' },
    rolldownOptions: {
      output: { postBanner: '/* Bundled dependency notices: /assets/THIRD_PARTY_LICENSES.md */' },
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
