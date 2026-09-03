/** Служебный токен только на сервере Next.js. В бандл браузера не попадает. */

export function internalTokenHeaders(): HeadersInit {
  const token = process.env.INTERNAL_SERVICE_TOKEN ?? "";
  if (!token) {
    return {};
  }
  return { "X-Internal-Token": token };
}
