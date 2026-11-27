import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { configuration, rifkiMiddleware } from "./server/rifki.mjs";

function rifki(env: NodeJS.ProcessEnv): Plugin {
  const config = configuration(env);
  return {
    name: "rifki-explicit-opt-in",
    configureServer(server) {
      server.middlewares.use(rifkiMiddleware({ config }));
    },
    configurePreviewServer(server) {
      server.middlewares.use(rifkiMiddleware({ config }));
    },
  };
}

export default defineConfig(({ mode }) => ({
  // RIFKI_* are server-only. Never change envPrefix to expose these to client JS.
  plugins: [
    react(),
    rifki({ ...loadEnv(mode, process.cwd(), "RIFKI_"), ...process.env }),
  ],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: [".e2b.app", "localhost", "127.0.0.1"],
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
    strictPort: true,
    allowedHosts: [".e2b.app", "localhost", "127.0.0.1"],
  },
  build: { outDir: "dist", sourcemap: false },
}));
