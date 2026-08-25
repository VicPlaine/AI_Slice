export interface VideoSelectionInput {
  taskFilename: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
}

export interface VideoSelectionResult {
  isVideoLike: boolean;
  isLikelyMatch: boolean;
  warning: string | null;
}

const VIDEO_FILE_PATTERN = /\.(mp4|mov|mkv|avi|flv|wmv|ts|m4v)$/i;

function normalizeBaseName(name: string): string {
  return name
    .toLowerCase()
    .replace(/\.[^.]+$/, '')
    .replace(/[\s._-]+/g, '')
    .replace(/[()[\]【】]/g, '');
}

export function evaluateVideoSelection(
  input: VideoSelectionInput,
): VideoSelectionResult {
  const isVideoLike =
    input.mimeType.startsWith('video/') || VIDEO_FILE_PATTERN.test(input.fileName);

  if (!isVideoLike) {
    return {
      isVideoLike: false,
      isLikelyMatch: false,
      warning: '请选择视频文件',
    };
  }

  const taskBase = normalizeBaseName(input.taskFilename);
  const fileBase = normalizeBaseName(input.fileName);
  const isLikelyMatch =
    taskBase === fileBase || taskBase.includes(fileBase) || fileBase.includes(taskBase);

  if (!isLikelyMatch) {
    return {
      isVideoLike: true,
      isLikelyMatch: false,
      warning: '你选择的可能不是本任务的原视频，切片时间点可能不匹配',
    };
  }

  return {
    isVideoLike: true,
    isLikelyMatch: true,
    warning: null,
  };
}
