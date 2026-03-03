import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import {
  generateSection,
  getGenerationStatus,
  type GenerationPendingResponse,
  type GenerationResponse,
  type GenerationSection,
  type GenerationStatusResponse,
} from "../api/books";

type SectionStatus = "idle" | "loading" | "success" | "error";

type UseGenerationSectionOptions = {
  auto?: boolean;
};

type UseGenerationSectionResult = {
  data: Record<string, unknown> | null;
  stored: boolean | null;
  status: SectionStatus;
  error: string | null;
  refresh: (force?: boolean) => Promise<void>;
};

const MAX_POLL_ATTEMPTS = 12;
const MAX_POLL_DURATION_MS = 90_000;
const INITIAL_BACKOFF_MS = 1800;
const BACKOFF_MULTIPLIER = 1.7;
const MAX_BACKOFF_MS = 8000;

const recentAutoRuns = new Map<string, number>();

function isPendingResponse(value: GenerationResponse | GenerationPendingResponse): value is GenerationPendingResponse {
  return "in_progress" in value;
}

function computeBackoffDelayMs(attempt: number): number {
  const rawDelay = INITIAL_BACKOFF_MS * Math.pow(BACKOFF_MULTIPLIER, Math.max(0, attempt - 1));
  return Math.min(MAX_BACKOFF_MS, Math.round(rawDelay));
}

function mapStatusErrorMessage(response: GenerationStatusResponse): string {
  if (response.status === "failed") {
    if (response.error_code) {
      return `Generation failed (${response.error_code}).`;
    }
    return "Generation failed.";
  }
  return "Still generating. Please try again.";
}

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 502) {
      return "Generation failed. Please retry.";
    }
    if (error.status === 429) {
      return "Too many requests. Please wait and try again.";
    }
    return `Request failed (${error.status}).`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected generation error.";
}

export function useGenerationSection(
  workId: string,
  section: GenerationSection,
  opts: UseGenerationSectionOptions = {},
): UseGenerationSectionResult {
  const auto = opts.auto ?? true;
  const key = `${workId}:${section}`;

  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [stored, setStored] = useState<boolean | null>(null);
  const [status, setStatus] = useState<SectionStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const runIdRef = useRef(0);
  const retryTimerRef = useRef<number | null>(null);

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current !== null) {
      window.clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, []);

  const pollUntilComplete = useCallback(async (activeRunId: number, startedAtMs: number) => {
    for (let attempt = 1; attempt <= MAX_POLL_ATTEMPTS; attempt += 1) {
      if (activeRunId !== runIdRef.current) {
        return null;
      }
      if (Date.now() - startedAtMs > MAX_POLL_DURATION_MS) {
        return null;
      }

      const statusResponse = await getGenerationStatus(workId, section);
      if (activeRunId !== runIdRef.current) {
        return null;
      }

      if (statusResponse.status === "complete") {
        return statusResponse;
      }
      if (statusResponse.status === "failed") {
        setStatus("error");
        setError(mapStatusErrorMessage(statusResponse));
        return null;
      }
      if (statusResponse.status === "missing") {
        setStatus("error");
        setError("Generation record was not found.");
        return null;
      }

      const serverDelay = statusResponse.retry_after_ms;
      const backoffDelay = computeBackoffDelayMs(attempt);
      const waitMs = Math.max(backoffDelay, serverDelay);

      await new Promise<void>((resolve) => {
        retryTimerRef.current = window.setTimeout(() => resolve(), waitMs);
      });
      retryTimerRef.current = null;
    }

    return null;
  }, [section, workId]);

  const runRequest = useCallback(async (force: boolean) => {
    if (!workId) {
      setStatus("error");
      setError("Missing work ID.");
      return;
    }

    clearRetryTimer();
    runIdRef.current += 1;
    const activeRunId = runIdRef.current;
    const startedAtMs = Date.now();

    setStatus("loading");
    setError(null);

    try {
      const initialResponse = await generateSection(workId, section, { force });
      if (activeRunId !== runIdRef.current) {
        return;
      }

      if (!isPendingResponse(initialResponse)) {
        setData(initialResponse.content ?? null);
        setStored(initialResponse.stored);
        setStatus("success");
        return;
      }

      const completion = await pollUntilComplete(activeRunId, startedAtMs);
      if (activeRunId !== runIdRef.current) {
        return;
      }
      if (!completion) {
        setStatus("error");
        setError("Still generating. Please try again.");
        return;
      }

      const finalResponse = await generateSection(workId, section, { force: false });
      if (activeRunId !== runIdRef.current) {
        return;
      }
      if (isPendingResponse(finalResponse)) {
        setStatus("error");
        setError("Still generating. Please try again.");
        return;
      }
      setData(finalResponse.content ?? null);
      setStored(finalResponse.stored);
      setStatus("success");
    } catch (requestError) {
      if (activeRunId !== runIdRef.current) {
        return;
      }
      setStatus("error");
      setError(toErrorMessage(requestError));
    }
  }, [clearRetryTimer, pollUntilComplete, section, workId]);

  const refresh = useCallback(async (force = false) => {
    await runRequest(force);
  }, [runRequest]);

  useEffect(() => {
    if (!auto || !workId) {
      return;
    }

    const now = Date.now();
    const lastStartedAt = recentAutoRuns.get(key) ?? 0;
    if (now - lastStartedAt < 3000) {
      return;
    }
    recentAutoRuns.set(key, now);
    void runRequest(false);

    return () => {
      clearRetryTimer();
      runIdRef.current += 1;
    };
  }, [auto, clearRetryTimer, key, runRequest, workId]);

  useEffect(() => () => {
    clearRetryTimer();
    runIdRef.current += 1;
  }, [clearRetryTimer]);

  return { data, stored, status, error, refresh };
}
