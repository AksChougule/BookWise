import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  GenerationPendingResponse,
  GenerationResponse,
  GenerationSection,
  GenerationStatusResponse,
} from "../src/api/books";
import { useGenerationSection } from "../src/hooks/useGenerationSection";

const { generateSectionMock, getGenerationStatusMock } = vi.hoisted(() => ({
  generateSectionMock: vi.fn<
    (workId: string, section: GenerationSection, opts?: { force?: boolean }) =>
      Promise<GenerationResponse | GenerationPendingResponse>
  >(),
  getGenerationStatusMock: vi.fn<
    (workId: string, section: GenerationSection) => Promise<GenerationStatusResponse>
  >(),
}));

vi.mock("../src/api/books", async () => {
  const actual = await vi.importActual<typeof import("../src/api/books")>("../src/api/books");
  return {
    ...actual,
    generateSection: generateSectionMock,
    getGenerationStatus: getGenerationStatusMock,
  };
});

function completeResponse(section: GenerationSection): GenerationResponse {
  return {
    book_id: "OL123W",
    section,
    prompt_version: "v1",
    provider: "openai",
    model: "gpt-5 mini",
    stored: true,
    status: "complete",
    content: { chapters: [{ title: "Chapter 1", summary: "Summary 1" }] },
  };
}

beforeEach(() => {
  vi.useFakeTimers();
  generateSectionMock.mockReset();
  getGenerationStatusMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useGenerationSection polling", () => {
  it("uses GET status polling when initial POST returns pending, then does one final POST fetch", async () => {
    generateSectionMock
      .mockResolvedValueOnce({
        stored: false,
        in_progress: true,
        retry_after_ms: 2000,
        status: "pending",
      })
      .mockResolvedValueOnce(completeResponse("chapters"));

    getGenerationStatusMock
      .mockResolvedValueOnce({ status: "pending", in_progress: true, retry_after_ms: 2000 })
      .mockResolvedValueOnce({ status: "complete", stored: true, updated_at: "2026-02-25T00:00:00Z", retry_after_ms: null });

    const { result } = renderHook(() =>
      useGenerationSection("OL123W", "chapters", { auto: true }),
    );

    await waitFor(() => {
      expect(generateSectionMock).toHaveBeenCalledTimes(1);
    });
    expect(getGenerationStatusMock).toHaveBeenCalledTimes(0);

    await vi.advanceTimersByTimeAsync(2000);
    await waitFor(() => {
      expect(getGenerationStatusMock).toHaveBeenCalledTimes(1);
    });
    expect(generateSectionMock).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(3100);
    await waitFor(() => {
      expect(getGenerationStatusMock).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(generateSectionMock).toHaveBeenCalledTimes(2);
    });
    expect(generateSectionMock).toHaveBeenNthCalledWith(2, "OL123W", "chapters", { force: false });
    expect(result.current.status).toBe("success");
  });

  it("stops polling after max attempts and sets timeout-like error", async () => {
    generateSectionMock.mockResolvedValue({
      stored: false,
      in_progress: true,
      retry_after_ms: 2000,
      status: "pending",
    });
    getGenerationStatusMock.mockResolvedValue({
      status: "pending",
      in_progress: true,
      retry_after_ms: 2000,
    });

    const { result } = renderHook(() =>
      useGenerationSection("OL456W", "chapters", { auto: true }),
    );

    await waitFor(() => {
      expect(generateSectionMock).toHaveBeenCalledTimes(1);
    });

    for (let i = 0; i < 12; i += 1) {
      await vi.advanceTimersByTimeAsync(8000);
    }

    await waitFor(() => {
      expect(getGenerationStatusMock).toHaveBeenCalledTimes(12);
      expect(result.current.status).toBe("error");
      expect(result.current.error).toBe("Still generating. Please try again.");
    });
    expect(generateSectionMock).toHaveBeenCalledTimes(1);
  });
});
