FROM node:22-bookworm-slim

WORKDIR /app

RUN npm install -g pnpm@11.17.0

EXPOSE 3000
ENTRYPOINT ["/bin/sh", "/app/scripts/entrypoint.sh"]
