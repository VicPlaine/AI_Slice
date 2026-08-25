import { FFmpeg } from '@ffmpeg/ffmpeg';
import { Zip, ZipPassThrough } from 'fflate';

import {
  buildLocalClipSpecs,
  type LocalClipExportFailure,
} from '../utils/localClipExport';
import {
  cleanupFfmpegPaths,
  createAbortError,
  createSharedFFmpegRuntime,
  ensureDir,
  mountWorkerFile,
  throwIfAborted,
  watchAbort,
} from './ffmpegRuntime';
import { resolveDefaultCoreUrls } from './ffmpegCoreUrls';

export interface LocalClipExportProgress {
  stage: 'loading' | 'reading' | 'uploading' | 'clipping' | 'zipping' | 'done';
  currentClip: number;
  totalClips: number;
  message: string;
}

interface ExportVideoClipsLocallyOptions {
  videoFile: File;
  clips: Array<{
    clip_index: number;
    title: string;
    start_time: number;
    end_time: number;
  }>;
  videoStartOffset?: number;
  onProgress?: (progress: LocalClipExportProgress) => void;
  signal?: AbortSignal;
}

interface LocalClipExportResult {
  blob: Blob;
  succeeded: number;
  failed: LocalClipExportFailure[];
}

const clipExporterRuntime = createSharedFFmpegRuntime<FFmpeg>({
  createFFmpeg: () => new FFmpeg(),
  resolveCoreUrls: resolveDefaultCoreUrls,
});

export async function exportVideoClipsLocally({
  videoFile,
  clips,
  videoStartOffset = 0,
  onProgress,
  signal,
}: ExportVideoClipsLocallyOptions): Promise<LocalClipExportResult> {
  const ffmpeg = await clipExporterRuntime.getFFmpeg({
    onLoadProgress: (message) => {
      onProgress?.({
        stage: 'loading',
        currentClip: 0,
        totalClips: 0,
        message,
      });
    },
    loadingMessage: '正在加载本地切片引擎',
    readyMessage: null,
    signal,
  });
  // 先处理最大片段，避免 WASM 堆经历多轮扩容/碎片化后再申请最大连续缓冲区。
  const clipSpecs = buildLocalClipSpecs(clips, videoStartOffset)
    .sort((a, b) => b.duration - a.duration);
  const failed: LocalClipExportFailure[] = [];
  let succeeded = 0;
  let zipSettled = false;
  let zipController!: ReadableStreamDefaultController<Uint8Array>;
  const zipStream = new ReadableStream<Uint8Array>({
    start(controller) {
      zipController = controller;
    },
  });
  const zipBlobPromise = new Response(zipStream, {
    headers: { 'Content-Type': 'application/zip' },
  }).blob();
  void zipBlobPromise.catch(() => undefined);
  let finishZip!: () => void;
  let failZip!: (error: Error) => void;
  const zipDone = new Promise<void>((resolve, reject) => {
    finishZip = resolve;
    failZip = reject;
  });
  const zip = new Zip((error, data, final) => {
    if (error) {
      if (!zipSettled) {
        zipSettled = true;
        zipController.error(error);
        failZip(error);
      }
      return;
    }

    if (data.length > 0) {
      // 立即把 ZIP 分块交给浏览器的 Blob 管道，JS 不再保留全部切片数据。
      zipController.enqueue(data);
    }
    if (final && !zipSettled) {
      zipSettled = true;
      zipController.close();
      finishZip();
    }
  });
  const inputDir = '/input';
  const outputDir = '/output';
  let aborted = false;

  const stopWatchingAbort = watchAbort(signal, () => {
    aborted = true;
    ffmpeg.terminate();
    clipExporterRuntime.reset();
  });

  try {
    throwIfAborted(signal);

    onProgress?.({
      stage: 'reading',
      currentClip: 0,
      totalClips: clipSpecs.length,
      message: '正在读取视频文件',
    });

    await ensureDir(ffmpeg, inputDir);
    await ensureDir(ffmpeg, outputDir);
    const inputPath = await mountWorkerFile(ffmpeg, videoFile, inputDir);

    for (const [index, clip] of clipSpecs.entries()) {
      throwIfAborted(signal);

      onProgress?.({
        stage: 'clipping',
        currentClip: index + 1,
        totalClips: clipSpecs.length,
        message: `正在切片 ${index + 1} / ${clipSpecs.length}`,
      });

      const outputPath = `${outputDir}/${clip.outputName}`;

      try {
        const exitCode = await ffmpeg.exec(
          [
            '-ss',
            clip.startTime.toFixed(3),
            '-i',
            inputPath,
            '-t',
            clip.duration.toFixed(3),
            '-c',
            'copy',
            '-avoid_negative_ts',
            'make_zero',
            '-y',
            outputPath,
          ],
          -1,
          { signal },
        );

        if (exitCode !== 0) {
          throw new Error(`ffmpeg exit code ${exitCode}`);
        }

        const fileData = await ffmpeg.readFile(outputPath, 'binary', { signal });
        const zipEntry = new ZipPassThrough(clip.outputName);
        zip.add(zipEntry);
        zipEntry.push(fileData as Uint8Array, true);
        succeeded += 1;
        await ffmpeg.deleteFile(outputPath);
      } catch (error) {
        if (signal?.aborted) {
          throw createAbortError();
        }

        failed.push({
          clipIndex: clip.clipIndex,
          title: clip.title,
          reason: error instanceof Error ? error.message : String(error),
        });

        // FFmpeg.wasm 出现分配失败后实例通常已不可继续使用，停止本轮避免连锁失败。
        break;
      }
    }

    if (succeeded === 0) {
      const reason = failed[0]?.reason;
      throw new Error(reason ? `切片导出失败：${reason}` : '所有片段导出失败，未生成可下载文件');
    }

    onProgress?.({
      stage: 'zipping',
      currentClip: clipSpecs.length,
      totalClips: clipSpecs.length,
      message: '正在打包 ZIP',
    });

    zip.end();
    await zipDone;
    const result = {
      blob: await zipBlobPromise,
      succeeded,
      failed,
    };

    onProgress?.({
      stage: 'done',
      currentClip: clipSpecs.length,
      totalClips: clipSpecs.length,
      message: '准备下载',
    });

    return result;
  } catch (error) {
    if (aborted || signal?.aborted) {
      throw createAbortError();
    }
    throw error;
  } finally {
    stopWatchingAbort();

    await cleanupFfmpegPaths(ffmpeg, {
      mounts: [inputDir],
      directories: [outputDir, inputDir],
    });

    if (!zipSettled) {
      zip.terminate();
      zipSettled = true;
      zipController.close();
      finishZip();
    }

    // 每次导出都释放 WASM 堆；下一次操作会创建全新的 FFmpeg 实例。
    try {
      ffmpeg.terminate();
    } catch {
      // 取消操作时实例可能已由 abort 监听器终止。
    }
    clipExporterRuntime.reset();
  }
}
