import { redirect } from "next/navigation";

/** Старый URL операторской: Bitrix и закладки ведут в общий инбокс. */
export default function OperatorRoute() {
  redirect("/chat/support");
}
