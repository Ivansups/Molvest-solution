import { hash } from "bcryptjs";
import { DEMO_USERS } from "../src/lib/auth-user";
import { prisma } from "../src/lib/prisma";

async function main(): Promise<void> {
  const passwordHash = await hash("password123", 12);

  for (const user of DEMO_USERS) {
    await prisma.user.upsert({
      where: { email: user.email },
      update: {
        name: user.name,
        password: passwordHash,
        role: user.role,
      },
      create: {
        email: user.email,
        name: user.name,
        password: passwordHash,
        role: user.role,
      },
    });
  }
}

main()
  .catch((error: unknown) => {
    console.error("Не удалось подготовить демо-учётные записи.", error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
