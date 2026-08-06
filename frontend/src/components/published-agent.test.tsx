import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";

import { PublishedAgent } from "./published-agent";

const publicMocks = vi.hoisted(() => ({
  getAgent: vi.fn(),
  startRun: vi.fn(),
  getRun: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, publicApi: publicMocks };
});

const agent = {
  slug: "ocean-explorer",
  project_name: "Ocean Explorer",
  problem_to_solve: "Help learners understand ocean science from evidence.",
  intended_users: "Students learning ocean science",
  audience_age: "AGE_12_17",
  success_goal: "Give clear answers grounded in the uploaded source.",
  welcome_message: "What would you like to discover about the ocean?",
  version_number: 2,
  status: "PUBLISHED",
  builder_label: "Student Builder",
  knowledge_source: {
    title: "Ocean Literacy, Version 3.2 (2024)",
    author: "NOAA",
    license: "CC0 Public Domain",
    source_url: "https://repository.library.noaa.gov/view/noaa/67228",
  },
};

afterEach(() => vi.clearAllMocks());

describe("PublishedAgent", () => {
  it("renders allowlisted metadata and a validated cited answer", async () => {
    publicMocks.getAgent.mockResolvedValue(agent);
    publicMocks.startRun.mockResolvedValue({
      run_id: "run-1",
      run_token: "short-lived-token",
      phase: "QUEUED",
      poll_after_ms: 1,
    });
    publicMocks.getRun.mockResolvedValue({
      id: "run-1",
      phase: "COMPLETED",
      status: "COMPLETED",
      display_stage: "Answer ready",
      result: {
        type: "ANSWERED",
        answer: "The ocean moves heat and shapes climate.",
        citations: [{
          chunk_id: "chunk-1",
          filename: "ocean-literacy.pdf",
          page_number: 9,
          excerpt: "The ocean is a major influence on weather and climate.",
        }],
      },
      safe_error: null,
      retryable: false,
    });
    render(<PublishedAgent slug="ocean-explorer" />);

    expect(await screen.findByRole("heading", { name: "Ocean Explorer" })).toBeInTheDocument();
    expect(screen.getByText("✓ Approved")).toBeInTheDocument();
    expect(screen.getByText(/CC0 Public Domain/)).toBeInTheDocument();
    const composer = screen.getByLabelText("Your question");
    const chat = composer.closest(".public-chat");
    const about = screen.getByRole("complementary", { name: "What it is here to do" });
    expect(chat?.compareDocumentPosition(about)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    fireEvent.change(composer, {
      target: { value: "How does the ocean affect climate?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask Agent" }));
    expect(await screen.findByText(/moves heat and shapes climate/)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/ocean-literacy.pdf/));
    expect(screen.getByText(/major influence on weather/)).toBeInTheDocument();
    expect(publicMocks.getRun).toHaveBeenCalledWith("run-1", "short-lived-token");
  });

  it("shows retry timing when the public limiter rejects a request", async () => {
    publicMocks.getAgent.mockResolvedValue(agent);
    publicMocks.startRun.mockRejectedValue(
      new ApiError("This network has reached the public demo limit.", 429, "PUBLIC_RATE_LIMITED", null, true, 90),
    );
    render(<PublishedAgent slug="ocean-explorer" />);
    await screen.findByRole("heading", { name: "Ocean Explorer" });
    fireEvent.change(screen.getByLabelText("Your question"), {
      target: { value: "What is ocean literacy?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask Agent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in about 90 seconds");
    await waitFor(() => expect(screen.getByRole("button", { name: "Ask Agent" })).toBeEnabled());
  });
});
