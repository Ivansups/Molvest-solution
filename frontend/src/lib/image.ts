const MAX_SIDE = 1024;

export async function fileToCompressedBase64(file: File): Promise<string> {
  const dataUrl = await readAsDataUrl(file);
  const bitmap = await loadImage(dataUrl);
  const { width, height } = fitWithin(bitmap.width, bitmap.height, MAX_SIDE);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) {
    return dataUrl.split(",")[1] ?? "";
  }
  context.drawImage(bitmap, 0, 0, width, height);
  const compressed = canvas.toDataURL("image/jpeg", 0.85);
  return compressed.split(",")[1] ?? "";
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Не удалось прочитать файл"));
    reader.readAsDataURL(file);
  });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Не удалось открыть изображение"));
    image.src = src;
  });
}

export function fitWithin(
  width: number,
  height: number,
  maxSide: number,
): { width: number; height: number } {
  const longSide = Math.max(width, height);
  if (longSide <= maxSide) {
    return { width, height };
  }
  const scale = maxSide / longSide;
  return {
    width: Math.round(width * scale),
    height: Math.round(height * scale),
  };
}
