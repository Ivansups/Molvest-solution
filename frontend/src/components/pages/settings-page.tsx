import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Настройки</h1>
        <p className="mt-2 text-slate-500">Раздел доступен для просмотра структуры консоли.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Вне этапов 1-6</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-6 text-slate-500">
            API для изменения настроек ещё не опубликован. Данные на этой странице не
            загружаются и не отправляются в backend.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
