import { requestJson } from "./client";
import { endpoints } from "./endpoints";

export function getHealthRoot(): Promise<unknown> {
  return requestJson<unknown>(endpoints.healthRoot);
}

export function getHealthApi(): Promise<unknown> {
  return requestJson<unknown>(endpoints.healthApi);
}

export function getMetrics(): Promise<unknown> {
  return requestJson<unknown>(endpoints.metrics);
}
