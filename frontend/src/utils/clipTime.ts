const MIN_SIGNIFICANT_OFFSET_SECONDS = 1;

interface ClipDisplayRangeInput {
  startTime: number;
  endTime: number;
  videoStartOffset?: number;
  hasGeneratedClip?: boolean;
}

interface ClipDisplayRange {
  startTime: number;
  endTime: number;
}

/**
 * 音频直传模式下，后端存储的时间可能包含视频容器的 PTS 偏移。
 * 展示给剪映裁切时，应换算回从 0 开始的编辑器时间轴。
 */
export function getClipDisplayRange({
  startTime,
  endTime,
  videoStartOffset = 0,
  hasGeneratedClip = false,
}: ClipDisplayRangeInput): ClipDisplayRange {
  if (hasGeneratedClip || videoStartOffset <= MIN_SIGNIFICANT_OFFSET_SECONDS) {
    return { startTime, endTime };
  }

  return {
    startTime: Math.max(0, startTime - videoStartOffset),
    endTime: Math.max(0, endTime - videoStartOffset),
  };
}

export function formatClipTime(seconds: number): string {
  const safeSeconds = Math.max(0, seconds);
  const h = Math.floor(safeSeconds / 3600);
  const m = Math.floor((safeSeconds % 3600) / 60);
  const s = Math.floor(safeSeconds % 60);

  if (h > 0) {
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  return `${m}:${s.toString().padStart(2, '0')}`;
}
