# Frontend

Next.js 16 App Router. Run it in Docker with the rest of the stack:

```bash
make setup
# http://localhost:3000
```

Do not run `pnpm dev` on the host. The Compose `web` service installs deps
inside the container and proxies `/backend/*` to the API.

Host Node is only for `pnpm lint`, `pnpm typecheck` and `pnpm test`.

Tests live in `tests/`, not next to source files. `pnpm lint` runs ESLint on the whole frontend, including that folder.
