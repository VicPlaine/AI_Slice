import bundledCoreScriptUrl from '@ffmpeg/core?url';
import bundledCoreWasmUrl from '@ffmpeg/core/wasm?url';

import type { FFmpegCoreUrls } from './ffmpegRuntime';

const CORE_CANDIDATES = [
  {
    label: 'bundled @ffmpeg/core asset',
    scriptUrl: bundledCoreScriptUrl,
    wasmUrl: bundledCoreWasmUrl,
  },
  {
    label: 'public ffmpeg fallback',
    scriptUrl: '/ffmpeg/ffmpeg-core.js',
    wasmUrl: '/ffmpeg/ffmpeg-core.wasm',
  },
];

async function createBlobUrlWithValidation(assetUrl: string, mimeType: string): Promise<string> {
  const response = await fetch(assetUrl);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} when loading ${assetUrl}`);
  }

  if (mimeType === 'text/javascript') {
    const scriptSource = await response.text();
    if (scriptSource.trimStart().startsWith('<')) {
      throw new Error(`Expected JavaScript but received HTML from ${assetUrl}`);
    }
    return URL.createObjectURL(new Blob([scriptSource], { type: mimeType }));
  }

  const bytes = new Uint8Array(await response.arrayBuffer());
  const sniffedText = new TextDecoder().decode(bytes.slice(0, 32)).trimStart();
  if (sniffedText.startsWith('<')) {
    throw new Error(`Expected WebAssembly binary but received HTML from ${assetUrl}`);
  }

  return URL.createObjectURL(new Blob([bytes], { type: mimeType }));
}

export async function resolveDefaultCoreUrls(): Promise<FFmpegCoreUrls> {
  let lastError: unknown;

  for (const candidate of CORE_CANDIDATES) {
    try {
      const coreURL = await createBlobUrlWithValidation(candidate.scriptUrl, 'text/javascript');
      const wasmURL = await createBlobUrlWithValidation(candidate.wasmUrl, 'application/wasm');
      return { coreURL, wasmURL };
    } catch (error) {
      lastError = error;
      console.warn(`[FFmpegRuntime] Failed to load ${candidate.label}.`, error);
    }
  }

  const reason = lastError instanceof Error ? lastError.message : String(lastError ?? 'unknown error');
  throw new Error(
    `Unable to load FFmpeg core assets. Tried bundled assets and /ffmpeg fallback. ${reason}`,
  );
}
