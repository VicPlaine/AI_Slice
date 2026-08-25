import { useMemo, useRef, useState } from 'react';

import { formatFileSize } from '../services/audioExtractor';
import type { LocalClipExportProgress } from '../services/videoClipExporter';
import { evaluateVideoSelection } from '../utils/videoFileMatch';

interface LocalClipExportModalProps {
  taskFilename: string;
  clipCount: number;
  exporting: boolean;
  exportMessage: string;
  progress: LocalClipExportProgress | null;
  onClose: () => void;
  onConfirm: (file: File) => Promise<void>;
  onCancelExport: () => void;
}

export default function LocalClipExportModal({
  taskFilename,
  clipCount,
  exporting,
  exportMessage,
  progress,
  onClose,
  onConfirm,
  onCancelExport,
}: LocalClipExportModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const selectionResult = useMemo(() => {
    if (!selectedFile) return null;
    return evaluateVideoSelection({
      taskFilename,
      fileName: selectedFile.name,
      mimeType: selectedFile.type,
      sizeBytes: selectedFile.size,
    });
  }, [selectedFile, taskFilename]);

  const handleSelect = (file: File | null) => {
    if (!file || exporting) return;
    setSelectedFile(file);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    handleSelect(event.dataTransfer.files?.[0] ?? null);
  };

  const canStart = !!selectedFile && selectionResult?.isVideoLike;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/45 p-4 backdrop-blur-sm"
      onClick={() => !exporting && onClose()}
    >
      <div
        className="w-[520px] max-w-[92vw] rounded-xl border border-stone-300 bg-[#faf9f6] p-6 text-stone-900 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <p className="eyebrow mb-2">Local export</p>
        <h3 className="mb-1 text-xl font-semibold">一键切片</h3>
        <p className="mb-4 text-sm leading-6 text-stone-500">
          选择本任务对应的原视频并生成 {clipCount} 段切片。小文件由浏览器处理，大文件自动交给本机 FFmpeg 稳定导出；视频不会上传到云端。
        </p>

        <div
          className={`rounded-2xl border-2 border-dashed transition-all duration-200 p-5 mb-4 cursor-pointer ${
            isDragging
              ? 'border-teal-700 bg-teal-50'
              : 'border-stone-300 bg-white hover:border-teal-700'
          } ${exporting ? 'pointer-events-none opacity-70' : ''}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            if (!exporting) setIsDragging(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setIsDragging(false);
          }}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*,.mkv,.flv,.avi,.wmv,.ts,.m4v"
            className="hidden"
            disabled={exporting}
            onChange={(event) => handleSelect(event.target.files?.[0] ?? null)}
          />

          {selectedFile ? (
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-all text-sm font-medium text-stone-900">{selectedFile.name}</p>
                  <p className="mt-1 text-xs text-stone-500">
                    {formatFileSize(selectedFile.size)}
                    {selectionResult?.isLikelyMatch ? ' · 与当前任务匹配' : ''}
                  </p>
                </div>
                {!exporting && (
                  <button
                    type="button"
                    className="btn-secondary shrink-0 px-3 py-1.5 text-xs"
                    onClick={(event) => {
                      event.stopPropagation();
                      fileInputRef.current?.click();
                    }}
                  >
                    重新选择
                  </button>
                )}
              </div>

              {selectionResult?.warning && (
                <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  {selectionResult.warning}
                </p>
              )}
            </div>
          ) : (
            <div className="text-center py-3">
              <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full border border-teal-200 bg-teal-50">
                <svg className="h-7 w-7 text-teal-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <p className="text-sm font-medium text-stone-900">点击选择或拖入原视频文件</p>
              <p className="mt-2 text-xs text-stone-500">
                建议选择与任务文件名相同的原视频：<span className="break-all text-teal-800">{taskFilename}</span>
              </p>
            </div>
          )}
        </div>

        {progress && (
          <div className="mb-4 rounded-lg border border-stone-200 bg-white px-4 py-3">
            <p className="text-sm font-medium text-teal-800">{progress.message}</p>
            <p className="mt-1 text-xs text-stone-500">
              {progress.stage === 'clipping'
                ? `阶段：本机切片 · ${progress.currentClip}/${progress.totalClips}`
                : progress.stage === 'zipping'
                  ? '阶段：打包 ZIP'
                  : progress.stage === 'uploading'
                    ? '阶段：传输到 localhost 本机服务'
                  : progress.stage === 'done'
                    ? '阶段：准备下载'
                    : progress.stage === 'reading'
                      ? '阶段：读取视频'
                      : '阶段：加载引擎'}
            </p>
          </div>
        )}

        {exportMessage && (
          <p className="mb-4 rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs text-stone-600">
            {exportMessage}
          </p>
        )}

        <div className="flex gap-3 justify-end">
          {exporting ? (
            <button
              type="button"
              onClick={onCancelExport}
              className="px-4 py-2 text-sm text-orange-700 transition-colors hover:text-orange-900"
            >
              取消切片
            </button>
          ) : (
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-stone-500 transition-colors hover:text-stone-900"
            >
              关闭
            </button>
          )}

          <button
            type="button"
            disabled={!canStart || exporting}
            onClick={async () => {
              if (!selectedFile) return;
              await onConfirm(selectedFile);
            }}
            className="btn-primary px-5 py-2"
          >
            {exporting ? '切片中...' : '开始切片'}
          </button>
        </div>
      </div>
    </div>
  );
}
