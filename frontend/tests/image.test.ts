import { describe, expect, it } from "vitest";
import { fitWithin } from "@/src/lib/image";

describe("fitWithin", () => {
  it("keepsSmallImages", () => {
    expect(fitWithin(800, 600, 1024)).toEqual({ width: 800, height: 600 });
  });

  it("scalesLongSideToMax", () => {
    expect(fitWithin(2048, 1024, 1024)).toEqual({ width: 1024, height: 512 });
  });
});
