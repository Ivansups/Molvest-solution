import { AlertCircle, ServerCrash } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";

export function ApiStateCard({
  title,
  description,
  detail,
  actionHref,
  actionLabel,
}: {
  title: string;
  description: string;
  detail?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <Card className="rounded-[28px]">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-secondary/10 text-secondary">
            {detail ? (
              <AlertCircle className="h-5 w-5" />
            ) : (
              <ServerCrash className="h-5 w-5" />
            )}
          </div>
          <div>
            <CardTitle>{title}</CardTitle>
            <p className="mt-1 text-sm text-slate-500">{description}</p>
          </div>
        </div>
      </CardHeader>
      {detail || actionHref ? (
        <CardContent className="space-y-4">
          {detail ? (
            <div className="rounded-[20px] border border-border/70 bg-slate-50/80 p-4 text-sm leading-6 text-slate-500">
              {detail}
            </div>
          ) : null}
          {actionHref && actionLabel ? (
            <Button variant="outline" asChild>
              <Link to={actionHref}>{actionLabel}</Link>
            </Button>
          ) : null}
        </CardContent>
      ) : null}
    </Card>
  );
}
