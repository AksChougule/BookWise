import { requestJson } from "./client";
import { endpoints } from "./endpoints";

export type CuratedBook = {
  id: string | null;
  source: string;
  title: string;
  author: string;
};

export function getCuratedRandom(): Promise<{ work_id: string } | CuratedBook> {
  return requestJson<{ work_id: string } | CuratedBook>(endpoints.curatedRandom);
}
