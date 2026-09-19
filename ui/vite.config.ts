import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { dataPlugin } from './server/data-plugin'

export default defineConfig({
  plugins: [react(), dataPlugin()],
  server: { port: 5173, host: '127.0.0.1' },
})
