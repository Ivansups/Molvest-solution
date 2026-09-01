"use client";

import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider as ToastPrimitiveProvider,
  ToastTitle,
  ToastViewport,
} from "@/src/components/ui/toast";

type ToastVariant = "default" | "destructive";

interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastContextValue {
  toast: (payload: Omit<ToastItem, "id">) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const value = {
    toast(payload: Omit<ToastItem, "id">) {
      const id = crypto.randomUUID();
      setItems((current) => [...current, { ...payload, id }]);
      window.setTimeout(() => {
        setItems((current) => current.filter((item) => item.id !== id));
      }, 4000);
    },
  };

  return (
    <ToastContext.Provider value={value}>
      <ToastPrimitiveProvider swipeDirection="right">
        {children}
        {items.map((item) => (
          <Toast
            key={item.id}
            open
            onOpenChange={(open) => {
              if (!open) {
                setItems((current) =>
                  current.filter((toastItem) => toastItem.id !== item.id),
                );
              }
            }}
            variant={item.variant}
          >
            <div className="grid gap-1">
              <ToastTitle>{item.title}</ToastTitle>
              {item.description ? (
                <ToastDescription>{item.description}</ToastDescription>
              ) : null}
            </div>
            <ToastClose />
          </Toast>
        ))}
        <ToastViewport />
      </ToastPrimitiveProvider>
    </ToastContext.Provider>
  );
}

export function useToastContext() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToastContext must be used within ToastProvider");
  }
  return context;
}
