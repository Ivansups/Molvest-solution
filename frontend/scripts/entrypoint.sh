#!/bin/sh
set -eu

if [ ! -f node_modules/next/dist/bin/next ]; then
  echo "Installing frontend deps inside the container..."
  pnpm install --frozen-lockfile
fi

echo "Applying auth migrations..."
pnpm exec prisma migrate deploy
echo "Seeding staff accounts..."
pnpm exec prisma db seed

exec pnpm exec next dev --hostname 0.0.0.0 --port 3000
