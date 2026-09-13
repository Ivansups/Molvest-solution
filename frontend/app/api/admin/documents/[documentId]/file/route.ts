import { NextResponse } from "next/server";
import { proxyAdminApi, requireAuthenticatedUser } from "@/src/lib/admin-api";

type Params = Promise<{ documentId: string }>;

export async function POST(
  request: Request,
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
  const scope = new URLSearchParams({ installation_id: user.installationId });
  return proxyAdminApi(`/api/documents/${documentId}/file?${scope.toString()}`, {
    method: "POST",
    body: await request.formData(),
  });
}
