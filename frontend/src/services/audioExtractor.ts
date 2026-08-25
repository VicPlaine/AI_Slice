/**
 * 浏览器端音频提取器 — 使用 FFmpeg.wasm 从视频中提取音频
 *
 * 提取参数与后端 extract_audio() 完全一致：
 * 16kHz mono MP3 64kbps（语音转写最优参数）
 *
 * 2.5 GB 视频 → ~30 MB MP3，上传体积缩减 99%
 *
 * 使用 WORKERFS 挂载 File 对象，避免将整个视频加载进 WASM 内存（解决大文件 OOM）
 */

import { FFmpeg } from '@ffmpeg/ffmpeg';

import {
  cleanupFfmpegPaths,
  createAbortError,
  createSharedFFmpegRuntime,
  mountWorkerFile,
  throwIfAborted,
  watchAbort,
} from './ffmpegRuntime';
import { resolveDefaultCoreUrls } from './ffmpegCoreUrls';

const audioRuntime = createSharedFFmpegRuntime<FFmpeg>({
  createFFmpeg: () => new FFmpeg(),
  resolveCoreUrls: resolveDefaultCoreUrls,
});

/** FFmpeg.wasm 加载状态 */
export type LoadState = 'idle' | 'loading' | 'ready' | 'error';

/** 进度回调 */
export interface ExtractProgress {
  /** 0-1 之间的进度值 */
  ratio: number;
  /** 当前阶段描述 */
  message: string;
}

/**
 * 从视频文件中提取音频（浏览器端，不上传视频到服务器）
 *
 * 使用 WORKERFS 挂载 File 对象：文件不会被整体读入内存，
 * FFmpeg 按需从原始 File handle 惰性读取数据，内存占用仅为处理缓冲区大小。
 * 这使得即使 4GB+ 的视频文件也能在浏览器中处理而不会 OOM。
 *
 * @param videoFile - 用户选择的视频 File 对象
 * @param onProgress - 进度回调 (0-1)
 * @returns MP3 Blob + 文件名
 */
export async function extractAudio(
  videoFile: File,
  onProgress?: (progress: ExtractProgress) => void,
  signal?: AbortSignal,
): Promise<{ blob: Blob; filename: string; startOffset: number; videoDuration: number | null }> {
  onProgress?.({ ratio: 0, message: '正在初始化音频引擎...' });

  const instance = await audioRuntime.getFFmpeg({
    onLoadProgress: (msg) => {
      onProgress?.({ ratio: 0.05, message: msg });
    },
    loadingMessage: '正在加载音频引擎...',
    readyMessage: '音频引擎就绪',
    signal,
  });

  // 监听处理进度
  const progressHandler = ({ progress: ratio }: { progress: number }) => {
    // FFmpeg.wasm progress 范围 0-1
    const clampedRatio = Math.min(Math.max(ratio, 0), 1);
    onProgress?.({
      ratio: 0.1 + clampedRatio * 0.85, // 10%~95% 是提取阶段
      message: `正在提取音频... ${Math.round(clampedRatio * 100)}%`,
    });
  };
  instance.on('progress', progressHandler);

  const MOUNT_POINT = '/input';
  const outputName = '/output.mp3';
  let aborted = false;

  const stopWatchingAbort = watchAbort(signal, () => {
    aborted = true;
    instance.terminate();
    audioRuntime.reset();
  });

  try {
    throwIfAborted(signal);

    // 1. 用 WORKERFS 挂载视频文件（零拷贝，惰性读取，不占 WASM 堆内存）
    //    对比旧方案 fetchFile() + writeFile()：那会把整个文件复制到 WASM 内存里，
    //    2.5 GB 视频 → 需要 ~5 GB 内存（Uint8Array + WASM FS 各一份），直接 OOM。
    //    WORKERFS 通过 Emscripten 的虚拟文件系统直接引用浏览器的 File handle，
    //    FFmpeg 只在需要时读取对应的字节区间，内存占用降到几十 MB。
    onProgress?.({ ratio: 0.05, message: '正在挂载视频文件...' });

    // WORKERFS 挂载后，文件可通过 /input/<原始文件名> 访问
    const inputPath = await mountWorkerFile(instance, videoFile, MOUNT_POINT);

    // ── 探测视频 start_time（用于修正 OBS 分段录制的 PTS 偏移）──
    let startOffset = 0;
    let videoDuration: number | null = null;
    const logLines: string[] = [];
    const logHandler = ({ message }: { message: string }) => {
      logLines.push(message);
    };
    instance.on('log', logHandler);
    try {
      // 用 -t 0.01 只读极短的一段来获取文件信息，几乎瞬间完成
      await instance.exec(['-i', inputPath, '-t', '0.01', '-f', 'null', '-'], -1, signal ? { signal } : undefined);
    } catch {
      // 即使 exec 报错（无输出格式等），log 中已经包含了文件信息
    }
    instance.off('log', logHandler);

    // 从 FFmpeg log 中解析 start: XXXX.XXXX
    for (const line of logLines) {
      const durationMatch = line.match(/Duration:\s+(\d+):(\d+):([\d.]+)/);
      if (durationMatch && videoDuration === null) {
        const hours = parseInt(durationMatch[1], 10);
        const minutes = parseInt(durationMatch[2], 10);
        const seconds = parseFloat(durationMatch[3]);
        videoDuration = hours * 3600 + minutes * 60 + seconds;
      }

      const match = line.match(/start:\s+([\d.]+)/);
      if (match) {
        const parsed = parseFloat(match[1]);
        if (parsed > 1) {  // 忽略极小偏移（<1s 通常是编码延迟，不是 PTS 偏移）
          startOffset = parsed;
          console.log(`[AudioExtractor] Detected video start_time: ${startOffset}s`);
        }
        break;
      }
    }

    onProgress?.({ ratio: 0.1, message: '开始提取音频...' });

    // 2. 执行音频提取（参数与后端 extract_audio 一致）
    await instance.exec(
      [
        '-i', inputPath,
        '-vn',                   // 去掉视频流
        '-acodec', 'libmp3lame', // MP3 编码
        '-ar', '16000',          // 16kHz 采样率
        '-ac', '1',              // 单声道
        '-b:a', '64k',           // 64kbps 码率
        outputName,
      ],
      -1,
      signal ? { signal } : undefined,
    );

    // 3. 读取输出文件（MP3 通常只有 ~30 MB，在内存中没问题）
    onProgress?.({ ratio: 0.95, message: '正在打包音频文件...' });
    const data = await instance.readFile(outputName, 'binary', signal ? { signal } : undefined);

    // 4. 清理：卸载 WORKERFS + 删除挂载点目录 + 删除输出文件
    await cleanupFfmpegPaths(instance, {
      mounts: [MOUNT_POINT],
      directories: [MOUNT_POINT],
      files: [outputName],
    });

    // data 可能是 SharedArrayBuffer 支持的 Uint8Array，需复制到普通 ArrayBuffer
    const uint8 = new Uint8Array(data as Uint8Array);
    const blob = new Blob([uint8.buffer], { type: 'audio/mpeg' });
    const audioFilename = videoFile.name.replace(/\.[^/.]+$/, '') + '.mp3';

    onProgress?.({ ratio: 1, message: '音频提取完成！' });

    return { blob, filename: audioFilename, startOffset, videoDuration };
  } catch (error) {
    // 出错时也要尝试卸载，避免下次挂载失败
    await cleanupFfmpegPaths(instance, {
      mounts: [MOUNT_POINT],
      directories: [MOUNT_POINT],
      files: [outputName],
    });
    if (aborted || signal?.aborted) {
      throw createAbortError();
    }
    throw error;
  } finally {
    stopWatchingAbort();
    // 移除 progress 监听，避免内存泄漏
    instance.off('progress', progressHandler);
    if (aborted || signal?.aborted) {
      audioRuntime.reset();
    }
  }
}

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB';
}
