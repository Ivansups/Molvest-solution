"use client";

import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { BrowserRouter } from "react-router-dom";
import App from "@/src/App";
import { AppProvider } from "@/src/store/app-context";
import { ToastProvider } from "@/src/store/toast-context";
import { Spinner } from "@/src/components/ui/spinner";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: false,
    },
  },
});

export default function MainApp() {
  const isClient = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AppProvider>
        <ToastProvider>
          {isClient ? (
            <BrowserRouter>
              <App />
            </BrowserRouter>
          ) : (
            <div className="flex min-h-screen items-center justify-center">
              <Spinner className="h-6 w-6" />
            </div>
          )}
        </ToastProvider>
      </AppProvider>
    </QueryClientProvider>
  );
}
