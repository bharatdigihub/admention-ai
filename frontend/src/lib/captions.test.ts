import { describe, expect, it } from "vitest";
import { parseJson3Captions, parseWebVtt } from "./captions";

describe("caption parsers", () => {
  it("parses YouTube WebVTT cues", () => {
    const cues = parseWebVtt(`WEBVTT

00:00:43.120 --> 00:00:45.840
Never gonna give you up
`);
    expect(cues).toHaveLength(1);
    expect(cues[0].start).toBeCloseTo(43.12);
    expect(cues[0].duration).toBeCloseTo(2.72);
    expect(cues[0].text).toBe("Never gonna give you up");
  });

  it("parses json3 caption events", () => {
    const cues = parseJson3Captions({
      events: [{ tStartMs: 1000, dDurationMs: 2000, segs: [{ utf8: "Hello from Piped" }] }],
    });
    expect(cues[0]).toEqual({ start: 1, duration: 2, text: "Hello from Piped" });
  });
});
