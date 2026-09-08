/** Поколение локального гостевого сеанса: stale-запросы после reset. */

/** Ответ относится к уже сброшенному гостевому сеансу. */
export function isStaleGuestGeneration(
  requestGeneration: number,
  currentGeneration: number,
): boolean {
  return requestGeneration !== currentGeneration;
}

/** Текущий гостевой сеанс ещё ждёт ответ на отправку. */
export function isActiveGuestSend(
  pendingGeneration: number | null,
  currentGeneration: number,
): boolean {
  return pendingGeneration === currentGeneration;
}
