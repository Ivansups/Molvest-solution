/** Единый контур базы знаний для гостевого чата и консоли поддержки. */
export const WORKSPACE_ID =
  process.env.NEXT_PUBLIC_WORKSPACE_ID?.trim() ||
  "7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11";

/** Обратная совместимость с существующими импортами установки. */
export const DEFAULT_INSTALLATION_ID = WORKSPACE_ID;
