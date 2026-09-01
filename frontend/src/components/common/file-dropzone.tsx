import { FileImage, FileText, UploadCloud } from "lucide-react";
import { useDropzone } from "react-dropzone";
import { cn } from "@/src/lib/utils";

interface FileDropzoneProps {
  accept: Record<string, string[]>;
  description: string;
  fileName?: string;
  onFileSelect: (file: File) => void;
}

export function FileDropzone({
  accept,
  description,
  fileName,
  onFileSelect,
}: FileDropzoneProps) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept,
    maxFiles: 1,
    onDropAccepted(files) {
      const [file] = files;
      if (file) {
        onFileSelect(file);
      }
    },
  });

  const Icon = Object.keys(accept).some((item) => item.startsWith("image/"))
    ? FileImage
    : FileText;

  return (
    <div
      {...getRootProps()}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-border bg-slate-50 px-6 py-10 text-center transition-colors",
        isDragActive && "border-primary bg-primary/5",
      )}
    >
      <input {...getInputProps()} />
      <div className="rounded-full bg-white p-3 text-secondary shadow-sm">
        <UploadCloud className="h-5 w-5" />
      </div>
      <p className="mt-4 text-sm font-medium text-secondary">
        Перетащите файл или нажмите для выбора
      </p>
      <p className="mt-2 text-sm text-slate-500">{description}</p>
      <div className="mt-4 flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs text-slate-500">
        <Icon className="h-3.5 w-3.5" />
        {fileName ?? "Файл ещё не выбран"}
      </div>
    </div>
  );
}

