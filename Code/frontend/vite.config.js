import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { readFileSync, existsSync, cpSync, rmSync } from 'fs'
import { resolve } from 'path'

// Build-time checks per 08_Deployment_Spec.md
function buildChecksPlugin() {
  return {
    name: 'traineta-build-checks',
    buildStart() {
      const isProduction = process.env.NODE_ENV === 'production'

      // D3a: check VITE_API_BASE_URL
      const apiUrl = process.env.VITE_API_BASE_URL
      if (!apiUrl) {
        if (isProduction) {
          console.info('\x1b[36m[TrainETA] VITE_API_BASE_URL is not set — building with same-origin relative URLs (supports any domain/IP automatically).\x1b[0m')
        } else {
          console.info('\x1b[33m[TrainETA] VITE_API_BASE_URL is not set — dev server using http://localhost:8000.\x1b[0m')
        }
      }

      // D3b: verify demo-fallback.json has entries
      const dir = typeof import.meta.dirname !== 'undefined' ? import.meta.dirname : resolve('.')
      const fallbackPath = resolve(dir, 'src/assets/demo-fallback.json')
      if (!existsSync(fallbackPath)) {
        this.error('[TrainETA] demo-fallback.json is missing from src/assets/. Run the gen_fallback.py script first.')
      } else {
        try {
          const fb = JSON.parse(readFileSync(fallbackPath, 'utf-8'))
          const count = Object.keys(fb.predictions || {}).length
          if (count === 0) {
            this.error('[TrainETA] demo-fallback.json has zero predictions. The mandatory offline-fallback path would be broken.')
          }
          console.info(`\x1b[32m[TrainETA] demo-fallback.json OK (${count} trains)\x1b[0m`)
        } catch (e) {
          this.error(`[TrainETA] demo-fallback.json could not be parsed: ${e.message}`)
        }
      }
    },
    closeBundle() {
      const dir = typeof import.meta.dirname !== 'undefined' ? import.meta.dirname : resolve('.')
      const distDir = resolve(dir, 'dist')
      const deployDir = resolve(dir, '../Deployment')
      if (existsSync(distDir) && existsSync(deployDir)) {
        rmSync(resolve(deployDir, 'assets'), { recursive: true, force: true })
        cpSync(distDir, deployDir, { recursive: true, force: true })
        console.info('\x1b[32m[TrainETA] Deployment files automatically updated in: Deployment/\x1b[0m')
      }
    }
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), buildChecksPlugin()],
  build: {
    chunkSizeWarningLimit: 25000,
  },
})
