import { defineConfig } from "vite";
export default defineConfig({
  base: "./",
  esbuild: {
    target: "es2022" },
  build: {
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks: {
          graph: ["3d-force-graph", "three", "three-spritetext"],
          math: ["katex"],
        },
      },
    },
  },
});
