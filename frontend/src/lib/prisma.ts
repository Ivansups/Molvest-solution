import { PrismaClient } from "@prisma/client";
import { isNextProductionBuild } from "@/src/lib/build-phase";

const globalForPrisma = globalThis as {
  prisma?: PrismaClient;
};

const BUILD_DATABASE_URL = "postgresql://build:build@127.0.0.1:5432/build";

function resolveDatabaseUrl(): string {
  const authDatabaseUrl = process.env.AUTH_DATABASE_URL?.trim();
  if (authDatabaseUrl) {
    return authDatabaseUrl;
  }

  const databaseUrl = process.env.DATABASE_URL?.trim();
  if (databaseUrl?.startsWith("postgresql+asyncpg://")) {
    return databaseUrl.replace("postgresql+asyncpg://", "postgresql://");
  }

  if (databaseUrl) {
    return databaseUrl;
  }

  // Во время next build PrismaClient может импортироваться для анализа route/page.
  // Подменяем URL только для фазы сборки, чтобы не требовать живую auth-БД.
  if (isNextProductionBuild()) {
    return BUILD_DATABASE_URL;
  }

  throw new Error("AUTH_DATABASE_URL is not set");
}

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    datasources: {
      db: {
        url: resolveDatabaseUrl(),
      },
    },
  });

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}
