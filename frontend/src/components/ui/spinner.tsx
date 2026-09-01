import { LoaderCircle } from "lucide-react";
import { cn } from "@/src/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle className={cn("h-5 w-5 animate-spin text-primary", className)} />;
}

