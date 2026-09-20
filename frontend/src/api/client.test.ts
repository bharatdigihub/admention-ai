import { describe, expect, it } from "vitest";
import { api } from "./client";

describe("api client", () => {
  it("uses a relative base URL for local Vite proxy by default", () => {
    expect(api.defaults.timeout).toBe(120000);
  });
});
