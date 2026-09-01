#!/bin/sh
# Bind-mount ./frontend перекрывает образ. Том node_modules хранит linux-зависимости.
set -eu

if [ ! -f node_modules/next/dist/bin/next ]; then
  echo "Installing frontend deps inside the container..."
  pnpm install --frozen-lockfile
fi

exec pnpm exec next dev --hostname 0.0.0.0 --port 3000
