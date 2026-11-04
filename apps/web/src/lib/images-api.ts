import { request, uploadFile } from "./api";

export interface StudioImage {
  id: string;
  width: number;
  height: number;
  mime: string;
  size_bytes: number;
  original_name: string;
  created_at: string;
  /** A resume, or a saved version of one, still uses it, so it cannot be deleted yet. */
  used: boolean;
  /** Served only to the owner. */
  url: string;
}

export interface StudioImages {
  images: StudioImage[];
  count: number;
  max_images: number;
  max_bytes: number;
  used_bytes: number;
  accepted: string[];
}

const BASE = "/api/v1/studio/images";

/** Limits shown to the person. The server enforces the real ones. */
export const IMAGE_MAX_BYTES = 5 * 1024 * 1024;
export const IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"] as const;

export function fetchImages(signal?: AbortSignal): Promise<StudioImages> {
  return request<StudioImages>("GET", BASE, { signal });
}

export function uploadImage(file: File): Promise<StudioImage> {
  return uploadFile<StudioImage>(BASE, file);
}

export function deleteImage(id: string): Promise<void> {
  return request<void>("DELETE", `${BASE}/${encodeURIComponent(id)}`);
}

/** The address a picture is shown from. Only the signed-in owner can open it. */
export function imageUrl(id: string): string {
  return `${BASE}/${encodeURIComponent(id)}/file`;
}

export function formatMegabytes(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
