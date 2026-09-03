import { NextRequest, NextResponse } from "next/server";
import { proxyAdminApi, requireAuthenticatedUser } from "@/src/lib/admin-api";

export async function GET(request: NextRequest): Promise<Response> {
  const user = await requireAuthenticatedUser();
  if (!user) {
    return NextResponse.json(
      { detail: "Требуется сессия сотрудника." },
      { status: 401 },
    );
  }

  const searchParams = new URLSearchParams(request.nextUrl.searchParams);
  searchParams.set("installation_id", user.installationId);

  return proxyAdminApi(`/api/documents?${searchParams.toString()}`);
}

export async function POST(request: NextRequest): Promise<Response> {
  const user = await requireAuthenticatedUser();
  if (!user) {
    return NextResponse.json(
      { detail: "Требуется сессия сотрудника." },
      { status: 401 },
    );
  }

  const formData = await request.formData();
  formData.set("installation_id", user.installationId);

  return proxyAdminApi("/api/documents", {
    method: "POST",
    body: formData,
  });
}
