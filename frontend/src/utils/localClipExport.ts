export interface LocalClipSpec {
  clipIndex: number;
  title: string;
  startTime: number;
  endTime: number;
  duration: number;
  outputName: string;
}

export interface LocalClipExportFailure {
  clipIndex: number;
  title: string;
  reason: string;
}

export function buildLocalClipSpecs(
  clips: Array<{
    clip_index: number;
    title: string;
    start_time: number;
    end_time: number;
  }>,
  videoStartOffset = 0,
): LocalClipSpec[] {
  // 当视频有 PTS 偏移时（OBS 分段录制），数据库存储的时间包含偏移，
  // 但浏览器 FFmpeg.wasm 读取视频文件时 PTS 从 0 开始，需要减回偏移
  const offset = videoStartOffset > 1 ? videoStartOffset : 0;

  return clips
    .map((clip) => {
      const startTime = Math.max(0, clip.start_time - offset);
      const endTime = Math.max(0, clip.end_time - offset);
      const duration = endTime - startTime;

      return {
        clipIndex: clip.clip_index,
        title: clip.title,
        startTime,
        endTime,
        duration,
        outputName: `${String(clip.clip_index).padStart(2, '0')}_${sanitizeClipTitle(clip.title)}.mp4`,
      };
    })
    .filter((clip) => clip.duration > 0);
}

export function buildClipArchiveName(videoFilename: string): string {
  const baseName = videoFilename.replace(/\.[^.]+$/, '') || '视频切片';
  return `${baseName}_切片.zip`;
}

export function summarizeLocalClipExport(result: {
  succeeded: number;
  failed: LocalClipExportFailure[];
}): string {
  if (result.failed.length > 0) {
    return `已成功导出 ${result.succeeded} 段，失败 ${result.failed.length} 段`;
  }

  return '切片完成！已下载 ZIP 文件';
}

function sanitizeClipTitle(title: string): string {
  const cleaned = title.replace(/[/\\:*?"<>|]/g, '_').trim();
  return cleaned.length > 0 ? cleaned.slice(0, 50) : '未命名片段';
}
