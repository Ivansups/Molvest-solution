FROM node:22-bookworm-slim

WORKDIR /app

# Docker не достукивается до registry.npmjs.org (TLS reset / UND_ERR_SOCKET).
RUN npm install -g pnpm@11.17.0 --registry https://registry.npmmirror.com

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY scripts/entrypoint.sh /usr/local/bin/frontend-entrypoint.sh
RUN chmod +x /usr/local/bin/frontend-entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["/bin/sh", "/usr/local/bin/frontend-entrypoint.sh"]
