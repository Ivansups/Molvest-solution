import type { ReactNode } from "react";
import type { Metadata } from "next";
import { Providers } from "@/app/providers";
import { getSession } from "@/src/lib/session";
import "./globals.css";

export const metadata: Metadata = {
  title: "Molvest AI Support",
  description: "Интерфейс AI-агента техподдержки 1С для АО «Молвест»",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const user = await getSession();

  return (
    <html lang="ru" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <Providers user={user}>{children}</Providers>
      </body>
    </html>
  );
}
