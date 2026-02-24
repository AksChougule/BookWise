import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { getCuratedRandom } from "../api/curated";
import { ApiError } from "../api/client";
import { normalizeWorkId } from "../api/endpoints";

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `Could not fetch surprise book (${error.status}).`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Could not fetch surprise book.";
}

export function SurpriseMeButton() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onClick = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getCuratedRandom();
      const workId = normalizeWorkId(result);
      if (!workId) {
        setError("No valid work ID returned.");
        return;
      }
      navigate(`/book/${workId}`);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      <button type="button" className="btn" onClick={onClick} disabled={loading}>
        {loading ? "Finding..." : "Surprise Me"}
      </button>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
    </div>
  );
}
