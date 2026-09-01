"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { setClientSession } from "@/src/lib/client-session";
import { ToastProvider } from "@/src/store/toast-context";
import type { UserSession } from "@/src/types/domain";

export function Providers({
  children,
  user,
}: {
  children: ReactNode;
  user: UserSession | null;
}) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: false,
          },
        },
      }),
  );

  setClientSession(user);

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}
