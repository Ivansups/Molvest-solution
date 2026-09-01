import { format } from "date-fns";
import { ru } from "date-fns/locale";

export function formatDateTime(value: string) {
  return format(new Date(value), "dd MMM yyyy, HH:mm", { locale: ru });
}

export function formatDate(value: string) {
  return format(new Date(value), "dd MMM yyyy", { locale: ru });
}

export function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function formatSeconds(value: number) {
  if (value < 60) {
    return `${value} сек`;
  }

  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  return `${minutes} мин ${seconds} сек`;
}

