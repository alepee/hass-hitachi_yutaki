import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Default node environment is sufficient: the Cache API, R2 and
    // Analytics Engine bindings are stubbed with in-memory fakes in the
    // tests, so @cloudflare/vitest-pool-workers is intentionally not used
    // (keeps the worker's devDependencies minimal).
    environment: "node",
    include: ["test/**/*.test.ts"],
  },
});
