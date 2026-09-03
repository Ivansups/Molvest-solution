import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { PrismaAdapter } from "@auth/prisma-adapter";
import { compare } from "bcryptjs";
import { z } from "zod";
import { displayNameForRole, getSupportInstallationId, resolveUserRole } from "@/src/lib/auth-user";
import { prisma } from "@/src/lib/prisma";

/**
 * Свои claim-ы JWT: augmentation `next-auth/jwt` не доходит до `@auth/core/jwt`,
 * поэтому токен в колбэке остаётся нетипизированным.
 */
type SessionClaims = {
  id?: string;
  role?: string;
  installationId?: string;
};

const credentialsSchema = z.object({
  email: z.string().email().transform((value) => value.trim().toLowerCase()),
  password: z.string().min(1),
});

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: PrismaAdapter(prisma),
  // Credentials-провайдер не создаёт строку в auth_sessions: Auth.js всегда
  // выдаёт подписанную куку. При strategy "database" auth() искал бы её как
  // session_token и всегда возвращал null.
  session: {
    strategy: "jwt",
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

        const role = resolveUserRole(user.role);
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
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.role = user.role;
        token.installationId = user.installationId;
      }
      return token;
    },
    async session({ session, token }) {
      if (!session.user) {
        return session;
      }

      const claims = token as SessionClaims;
      session.user.id = claims.id ?? "";
      session.user.role = resolveUserRole(claims.role) ?? undefined;
      session.user.installationId =
        claims.installationId ?? getSupportInstallationId();

      return session;
    },
  },
});
