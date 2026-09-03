import { NextResponse } from "next/server";
import { proxyAdminApi, requireAuthenticatedUser } from "@/src/lib/admin-api";

type Params = Promise<{ documentId: string }>;

export async function POST(
  _request: Request,
  { params }: { params: Params },
): Promise<Response> {
  const user = await requireAuthenticatedUser();
  if (!user) {
    return NextResponse.json(
      { detail: "Требуется сессия сотрудника." },
      { status: 401 },
    );
  }

  const { documentId } = await params;
  return proxyAdminApi(`/api/documents/${documentId}/reindex`, {
    method: "POST",
  });
}
