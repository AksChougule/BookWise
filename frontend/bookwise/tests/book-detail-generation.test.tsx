import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";

import BookDetailPage from "../src/pages/BookDetailPage";
import type { GenerationPendingResponse, GenerationResponse, GenerationSection } from "../src/api/books";

const { generateSectionMock } = vi.hoisted(() => ({
  generateSectionMock: vi.fn<
    (workId: string, section: GenerationSection, opts?: { force?: boolean }) => Promise<GenerationResponse | GenerationPendingResponse>
  >(),
}));

vi.mock("../src/api/books", async () => {
  const actual = await vi.importActual<typeof import("../src/api/books")>("../src/api/books");
  return {
    ...actual,
    generateSection: generateSectionMock,
  };
});

vi.mock("../src/hooks/useBook", () => ({
  useBook: () => ({
    data: {
      id: "OL123W",
      title: "Atomic Habits",
      authors: ["James Clear"],
      description: "A practical guide to building good habits.",
      cover_url: null,
      subjects: ["Habits"],
      first_publish_year: 2018,
      source_urls: { openlibrary: "https://openlibrary.org/works/OL123W" },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

function renderBookDetail() {
  render(
    <MemoryRouter initialEntries={["/book/OL123W"]}>
      <Routes>
        <Route path="/book/:workId" element={<BookDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function successResponse(section: GenerationSection, stored: boolean, content: Record<string, unknown>): GenerationResponse {
  return {
    book_id: "OL123W",
    section,
    prompt_version: "v1",
    provider: "openai",
    model: "gpt-5.2",
    stored,
    status: "complete",
    content,
  };
}

beforeEach(() => {
  generateSectionMock.mockReset();
});

describe("Book detail generation sections", () => {
  it("shows Stored badge and regenerate uses force=true then updates to Generated", async () => {
    generateSectionMock.mockImplementation(async (_workId, section, opts) => {
      if (section === "overview") {
        return successResponse(
          "overview",
          opts?.force ? false : true,
          {
            overview: opts?.force ? "Freshly regenerated summary." : "Cached summary.",
            reading_time_minutes: 5,
          },
        );
      }
      if (section === "key_ideas") {
        return successResponse("key_ideas", true, { key_ideas: ["Idea one", "Idea two", "Idea three"] });
      }
      if (section === "chapters") {
        return successResponse("chapters", true, {
          chapters: [{ title: "Chapter 1", summary: "Summary one." }],
        });
      }
      return successResponse("critique", true, {
        strengths: ["Clear writing"],
        weaknesses: ["Light on depth"],
        who_should_read: ["Beginners"],
      });
    });

    renderBookDetail();

    const overviewHeading = await screen.findByRole("heading", { name: "Overview" });
    const overviewSection = overviewHeading.closest("section");
    expect(overviewSection).not.toBeNull();
    const overview = overviewSection as HTMLElement;

    await waitFor(() => {
      expect(within(overview).getByText("Stored")).toBeInTheDocument();
    });

    fireEvent.click(within(overview).getByRole("button", { name: "Regenerate" }));

    await waitFor(() => {
      expect(generateSectionMock).toHaveBeenCalledWith("OL123W", "overview", { force: true });
    });
    await waitFor(() => {
      expect(within(overview).getByText("Generated")).toBeInTheDocument();
    });
  });

  it("toggles key ideas collapsible section", async () => {
    generateSectionMock.mockImplementation(async (_workId, section) => {
      if (section === "overview") {
        return successResponse("overview", true, { overview: "Overview text", reading_time_minutes: 4 });
      }
      if (section === "key_ideas") {
        return successResponse("key_ideas", true, { key_ideas: ["First key idea", "Second key idea", "Third key idea"] });
      }
      if (section === "chapters") {
        return successResponse("chapters", true, {
          chapters: [{ title: "Chapter 1", summary: "Summary one." }],
        });
      }
      return successResponse("critique", true, {
        strengths: ["A"],
        weaknesses: ["B"],
        who_should_read: ["C"],
      });
    });

    renderBookDetail();

    const keyIdeasHeading = await screen.findByRole("heading", { name: "Key ideas" });
    const keyIdeasSection = keyIdeasHeading.closest("section");
    expect(keyIdeasSection).not.toBeNull();
    const keyIdeas = keyIdeasSection as HTMLElement;

    await waitFor(() => {
      expect(within(keyIdeas).getByText("First key idea")).toBeInTheDocument();
    });

    const collapseButton = within(keyIdeas).getByRole("button", { name: "Collapse" });
    expect(collapseButton).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(collapseButton);
    expect(collapseButton).toHaveAttribute("aria-expanded", "false");
    expect(within(keyIdeas).queryByText("First key idea")).not.toBeInTheDocument();
  });

  it("shows error and retries successfully", async () => {
    let keyIdeaCalls = 0;
    generateSectionMock.mockImplementation(async (_workId, section) => {
      if (section === "overview") {
        return successResponse("overview", true, { overview: "Overview text", reading_time_minutes: 4 });
      }
      if (section === "key_ideas") {
        keyIdeaCalls += 1;
        if (keyIdeaCalls === 1) {
          throw new Error("Failed to generate");
        }
        return successResponse("key_ideas", false, { key_ideas: ["Recovered idea"] });
      }
      if (section === "chapters") {
        return successResponse("chapters", true, {
          chapters: [{ title: "Chapter 1", summary: "Summary one." }],
        });
      }
      return successResponse("critique", true, {
        strengths: ["A"],
        weaknesses: ["B"],
        who_should_read: ["C"],
      });
    });

    renderBookDetail();

    const keyIdeasHeading = await screen.findByRole("heading", { name: "Key ideas" });
    const keyIdeasSection = keyIdeasHeading.closest("section");
    expect(keyIdeasSection).not.toBeNull();
    const keyIdeas = keyIdeasSection as HTMLElement;

    await waitFor(() => {
      expect(within(keyIdeas).getByText("Failed to generate")).toBeInTheDocument();
    });

    fireEvent.click(within(keyIdeas).getByRole("button", { name: "Retry" }));

    await waitFor(() => {
      expect(within(keyIdeas).getByText("Recovered idea")).toBeInTheDocument();
    });
  });
});
