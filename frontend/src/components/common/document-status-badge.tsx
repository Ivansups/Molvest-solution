import { Badge } from "@/src/components/ui/badge";
import { Spinner } from "@/src/components/ui/spinner";
import type { DocumentStatus } from "@/src/types/api";

/** Статус документа: у PENDING крутится индикатор индексации. */
export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <Badge className="gap-1.5" aria-busy={status === "PENDING"}>
      {status === "PENDING" ? (
        <Spinner className="h-3 w-3 text-secondary" />
      ) : null}
      {status}
    </Badge>
  );
}
