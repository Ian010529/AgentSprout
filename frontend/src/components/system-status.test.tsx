import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { SystemStatus } from "./system-status";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("moves from checking to ready using backend state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ready",
          checks: { sqlite: "ok", chroma: "ok", uploads: "ok", migrations: "ok" },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );

  render(<SystemStatus />);
  expect(screen.getByText("Checking the workshop…")).toBeInTheDocument();
  expect(await screen.findByText("Workshop ready")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Readiness checks" })).toBeInTheDocument();
});
