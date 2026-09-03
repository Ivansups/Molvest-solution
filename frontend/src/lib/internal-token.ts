/** Служебный токен только на сервере Next.js. В бандл браузера не попадает. */

export const INTERNAL_TOKEN_HEADER = "X-Internal-Token";

export function internalTokenHeaders(): HeadersInit {
  const token = process.env.INTERNAL_SERVICE_TOKEN ?? "";
  if (!token) {
    return {};
  }
  return { [INTERNAL_TOKEN_HEADER]: token };
}
