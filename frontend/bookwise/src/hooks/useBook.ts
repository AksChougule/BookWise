import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { getBook, normalizeBook, type BookViewModel } from "../api/books";

export type UseBookState = {
  data: BookViewModel | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
};

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return "Book not found.";
    }
    if (error.status === 408) {
      return "Request timed out. Please retry.";
    }
    return `Could not load book (${error.status}).`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Could not load book metadata.";
}

export function useBook(workId: string | undefined): UseBookState {
  const [data, setData] = useState<BookViewModel | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeControllerRef = useRef<AbortController | null>(null);

  const fetchBook = useCallback(async () => {
    if (!workId) {
      setData(null);
      setError("Invalid work ID.");
      setIsLoading(false);
      return;
    }

    activeControllerRef.current?.abort();
    const controller = new AbortController();
    activeControllerRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const raw = await getBook(workId, controller.signal);
      if (activeControllerRef.current !== controller) {
        return;
      }
      setData(normalizeBook(raw, workId));
    } catch (err) {
      if (controller.signal.aborted) {
        return;
      }
      setData(null);
      setError(toErrorMessage(err));
    } finally {
      if (activeControllerRef.current === controller) {
        setIsLoading(false);
      }
    }
  }, [workId]);

  useEffect(() => {
    void fetchBook();
  }, [fetchBook]);

  useEffect(
    () => () => {
      activeControllerRef.current?.abort();
    },
    [],
  );

  return { data, isLoading, error, refetch: fetchBook };
}
