import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  server: {
    open: true,
    host: "::",
    port: 8080,

    proxy: {
      "/app": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },

      "/auth": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },

      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
      },
    },
  },

  plugins: [react()],

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
