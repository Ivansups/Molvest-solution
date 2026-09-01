import { useToastContext } from "@/src/store/toast-context";

export function useToast() {
  return useToastContext();
}

