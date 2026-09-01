import { CalendarDays } from "lucide-react";
import { Input } from "@/src/components/ui/input";

interface DatePickerProps {
  value: string;
  onChange: (value: string) => void;
}

export function DatePicker({ value, onChange }: DatePickerProps) {
  return (
    <div className="relative">
      <CalendarDays className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
      <Input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="pl-9"
      />
    </div>
  );
}

