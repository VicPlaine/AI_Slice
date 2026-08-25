import { useEffect, useRef, useState } from 'react';

interface ProgressBarProps {
  progress: number;
  message: string;
  status: string;
  startedAt?: number; // Unix timestamp (秒)
  onCancel?: () => void;
  isCancelling?: boolean;
}

const STEPS = [
  { id: 'downloading', label: '准备源数据', detail: '正在校验已上传的音频资料...', start: 0, end: 15 },
  { id: 'transcribing', label: '千问转录', detail: '千问语音识别正在将音频转为文字...', start: 15, end: 60 },
  { id: 'analyzing', label: '内容分析', detail: '千问大模型正在分析转录文本，提取精彩片段...', start: 60, end: 90 },
  { id: 'clipping', label: '整理切点', detail: '正在校验并整理视频剪辑时间点...', start: 90, end: 95 },
  { id: 'uploading', label: '保存结果', detail: '正在保存切片方案和内容摘要...', start: 95, end: 100 },
];

function formatEta(seconds: number): string {
  if (seconds < 60) return `约 ${Math.ceil(seconds)} 秒`;
  if (seconds < 3600) return `约 ${Math.ceil(seconds / 60)} 分钟`;
  const h = Math.floor(seconds / 3600);
  const m = Math.ceil((seconds % 3600) / 60);
  return `约 ${h} 小时 ${m} 分钟`;
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m${s.toString().padStart(2, '0')}s`;
}

export default function ProgressBar({
  progress,
  message,
  status,
  startedAt,
  onCancel,
  isCancelling = false,
}: ProgressBarProps) {
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 计时器：每秒更新已用时间
  useEffect(() => {
    if (!startedAt || startedAt <= 0 || ['done', 'failed', 'canceled'].includes(status)) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    const tick = () => setElapsed(Math.max(0, Date.now() / 1000 - startedAt));
    tick();
    timerRef.current = setInterval(tick, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [startedAt, status]);

  // 当前步骤索引
  let currentStepIndex = 0;
  if (status === 'done') currentStepIndex = STEPS.length;
  else if (status === 'failed' || status === 'canceled') currentStepIndex = -1;
  else {
    const foundIndex = STEPS.findIndex(s => s.id === status);
    if (foundIndex !== -1) currentStepIndex = foundIndex;
  }

  const isFailed = status === 'failed';
  const isCanceled = status === 'canceled';
  const isDone = status === 'done';
  const isProcessing = !isFailed && !isCanceled && !isDone;

  const getStepProgress = (step: (typeof STEPS)[number]) => {
    if (isDone || progress >= step.end) return 100;
    if (progress <= step.start) return 0;
    return Math.min(99, Math.max(0, Math.round((progress - step.start) / (step.end - step.start) * 100)));
  };

  // ETA 计算
  let etaStr = '';
  if (isProcessing && progress > 5 && elapsed > 10) {
    const speed = progress / elapsed; // %/秒
    const remaining = (100 - progress) / speed;
    if (remaining > 0 && remaining < 86400) {
      etaStr = formatEta(remaining);
    }
  }

  return (
    <div className="glass-card p-6 md:p-8 mb-8">
      {/* 顶部：标题 + 百分比 + 时间信息 */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h3 className="text-xl font-semibold mb-1">
            {isFailed ? '任务执行失败' : isCanceled ? '任务已取消' : isDone ? '处理完成' : '内容处理中'}
          </h3>
          <p className={`text-sm ${isFailed ? 'text-red-700' : 'text-stone-500'}`}>
            {message}
          </p>
          {/* 时间行 */}
          {isProcessing && elapsed > 0 && (
            <div className="mt-2 flex items-center gap-4 text-xs text-stone-400">
              <span>已用 {formatElapsed(elapsed)}</span>
              {etaStr && (
                <>
                  <span className="text-slate-600">·</span>
                  <span className="text-teal-700">预计还需 {etaStr}</span>
                </>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-4">
          {!isFailed && !isCanceled && (
            <div className="font-mono text-3xl font-semibold text-orange-700">{progress}%</div>
          )}
          {isProcessing && onCancel && (
            <button
              type="button"
              onClick={onCancel}
              disabled={isCancelling}
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 disabled:cursor-wait disabled:opacity-60"
            >
              {isCancelling ? '正在停止…' : '停止分析'}
            </button>
          )}
        </div>
      </div>

      {/* 进度条 */}
      <div className="relative">
        <div className="h-2 w-full overflow-hidden rounded-full bg-stone-200">
          <div
            className={`h-full rounded-full transition-all duration-1000 ease-out relative ${
              isFailed
                ? 'bg-red-500'
                : 'bg-teal-700'
            }`}
            style={{ width: `${progress}%` }}
          >
            {/* 进度条尾部光晕 */}
            {isProcessing && (
              <div className="absolute right-0 top-1/2 h-5 w-5 -translate-y-1/2 animate-pulse rounded-full bg-teal-300/50" />
            )}
          </div>
        </div>

        {/* 步骤指示器 */}
        {!isFailed && !isCanceled && (
          <div className="mt-6 flex justify-between relative px-2">
            {STEPS.map((step, idx) => {
              const stepProgress = getStepProgress(step);
              const state =
                idx < currentStepIndex ? 'completed' :
                idx === currentStepIndex ? 'current' : 'upcoming';

              return (
                <div key={step.id} className="flex flex-col items-center w-1/5 relative z-10">
                  {/* 圆点 */}
                  <div
                    className={`w-6 h-6 rounded-full mb-2 flex items-center justify-center transition-all duration-500 ${
                      state === 'completed'
                        ? 'bg-teal-700 text-white'
                        : state === 'current'
                        ? 'bg-orange-600 text-white ring-4 ring-orange-100'
                        : 'border border-stone-300 bg-stone-100 text-stone-400'
                    }`}
                    style={
                      state === 'current'
                        ? {
                            background: '#c7592b',
                            animation: 'breathe 2s ease-in-out infinite',
                          }
                        : undefined
                    }
                  >
                    {state === 'completed' ? (
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : state === 'current' ? (
                      <div className="w-2 h-2 rounded-full bg-white" />
                    ) : (
                      <div className="w-1.5 h-1.5 rounded-full bg-current" />
                    )}
                  </div>
                  {/* 标签 */}
                  <span
                    className={`text-xs text-center font-medium leading-tight ${
                      state === 'completed'
                        ? 'text-teal-800'
                        : state === 'current'
                        ? 'text-orange-800'
                        : 'text-stone-400'
                    }`}
                  >
                    {step.label}
                  </span>
                  <span className={`mt-1 font-mono text-[11px] ${state === 'current' ? 'text-orange-700' : state === 'completed' ? 'text-teal-700' : 'text-stone-400'}`}>
                    {stepProgress}%
                  </span>
                  <div className="mt-1 h-1 w-12 overflow-hidden rounded-full bg-stone-200">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${state === 'current' ? 'bg-orange-600' : 'bg-teal-700'}`}
                      style={{ width: `${stepProgress}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 当前阶段详情卡片 */}
      {isProcessing && currentStepIndex >= 0 && currentStepIndex < STEPS.length && (
        <div className="mt-6 flex items-center gap-3 rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
          {/* 呼吸灯 */}
          <div className="relative flex-shrink-0">
            <span className="flex h-3 w-3">
              <span
                className="absolute inline-flex h-full w-full rounded-full opacity-75"
                style={{
                  background: '#1f766e',
                  animation: 'breathe 2s ease-in-out infinite',
                }}
              />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-teal-700" />
            </span>
          </div>
          <span className="text-sm text-stone-600">
            {STEPS[currentStepIndex].detail}
          </span>
        </div>
      )}

      {/* 呼吸灯 CSS 动画 */}
      <style>{`
        @keyframes breathe {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.15); }
        }
      `}</style>
    </div>
  );
}
