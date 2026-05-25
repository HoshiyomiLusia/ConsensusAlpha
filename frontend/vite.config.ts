import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const buildId = Date.now().toString(36);

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        entryFileNames: `assets/${buildId}/[name]-[hash].js`,
        chunkFileNames: `assets/${buildId}/[name]-[hash].js`,
        assetFileNames: `assets/${buildId}/[name]-[hash][extname]`
      }
    }
  },
  server: {
    port: 5173
  }
});
