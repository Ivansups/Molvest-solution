import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { PrismaAdapter } from "@auth/prisma-adapter";
import { compare } from "bcryptjs";
import { z } from "zod";
import { displayNameForRole, getSupportInstallationId, resolveUserRole } from "@/src/lib/auth-user";
import { prisma } from "@/src/lib/prisma";

const credentialsSchema = z.object({
  email: z.string().email().transform((value) => value.trim().toLowerCase()),
  password: z.string().min(1),
});

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: PrismaAdapter(prisma),
  session: {
    strategy: "database",
  },
  pages: {
    signIn: "/login",
  },
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(rawCredentials) {
        const parsed = credentialsSchema.safeParse(rawCredentials);
        if (!parsed.success) {
          return null;
        }

        const user = await prisma.user.findUnique({
          where: { email: parsed.data.email },
        });
        if (!user?.password) {
          return null;
        }

        const isValidPassword = await compare(parsed.data.password, user.password);
        if (!isValidPassword) {
          return null;
        }

        const role = resolveUserRole(user.email, user.role);
        if (!role) {
          return null;
        }

        return {
          id: user.id,
          email: user.email,
          name: user.name ?? displayNameForRole(role),
          role,
          installationId: getSupportInstallationId(),
        };
      },
    }),
  ],
  callbacks: {
    async session({ session, user }) {
      if (!session.user) {
        return session;
      }

      const role =
        resolveUserRole(
          user?.email ?? session.user.email ?? "",
          user?.role ?? null,
        ) ?? "admin";

      session.user.id = user?.id ?? "";
      session.user.role = role;
      session.user.installationId =
        user?.installationId ?? getSupportInstallationId();
      session.user.name = session.user.name ?? user?.name ?? displayNameForRole(role);
      session.user.email = session.user.email ?? user?.email ?? "";

      return session;
    },
  },
});
