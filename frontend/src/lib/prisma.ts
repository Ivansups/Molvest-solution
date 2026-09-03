import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as {
  prisma?: PrismaClient;
};

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
