import { useState } from 'react';
import type { TaskClip, EditingGuide } from '../types/task';
import { formatClipTime, getClipDisplayRange } from '../utils/clipTime';
import {
  generateCaptionSuggestions,
  generateEditingGuide,
  generateViralTitles,
  updateClipCaption,
  updateClipTitle,
} from '../services/api';
import EditingGuideModal from './EditingGuideModal';

export type ClipItemProps = TaskClip;

interface ClipCardProps {
  clip: ClipItemProps;
  videoStartOffset?: number;
}

export default function ClipCard({
  clip,
  videoStartOffset = 0,
}: ClipCardProps) {
  const [currentTitle, setCurrentTitle] = useState(clip.title);
  const [currentCaption, setCurrentCaption] = useState(clip.suggested_caption);
  const [captionSuggestions, setCaptionSuggestions] = useState<string[] | null>(null);
  const [isGeneratingCaption, setIsGeneratingCaption] = useState(false);
  const [replacingCaptionIndex, setReplacingCaptionIndex] = useState<number | null>(null);
  const [captionError, setCaptionError] = useState('');
  // 爆款标题状态
  const [viralTitles, setViralTitles] = useState<string[] | null>(
    clip.viral_titles || null,
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [showTitles, setShowTitles] = useState(!!clip.viral_titles?.length);
  const [genError, setGenError] = useState('');
  const [replacingTitleIndex, setReplacingTitleIndex] = useState<number | null>(null);

  // 剪辑思路状态
  const [editingGuide, setEditingGuide] = useState<EditingGuide | null>(
    clip.editing_guide || null,
  );
  const [isGeneratingGuide, setIsGeneratingGuide] = useState(false);
  const [showGuide, setShowGuide] = useState(!!clip.editing_guide);
  const [guideError, setGuideError] = useState('');
  const [guideModalOpen, setGuideModalOpen] = useState(false);

  const displayRange = getClipDisplayRange({
    startTime: clip.start_time,
    endTime: clip.end_time,
    videoStartOffset,
    hasGeneratedClip: Boolean(clip.download_url),
  });
  const copyableTimeRange =
    `${formatClipTime(displayRange.startTime)} - ${formatClipTime(displayRange.endTime)}`;

  const handleCopyCaption = () => {
    navigator.clipboard.writeText(currentCaption).then(() => {
      const btn = document.getElementById(`copy-btn-${clip.id}`);
      if (btn) {
        const original = btn.innerText;
        btn.innerText = '已复制!';
        setTimeout(() => { btn.innerText = original; }, 2000);
      }
    });
  };

  const handleGenerateViralTitles = async () => {
    setIsGenerating(true);
    setGenError('');
    try {
      const result = await generateViralTitles(clip.id);
      setViralTitles(result.viral_titles);
      setShowTitles(true);
    } catch (err) {
      console.error('生成爆款标题失败', err);
      setGenError('生成失败，请重试');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyTitle = (title: string, index: number) => {
    navigator.clipboard.writeText(title).then(() => {
      const btn = document.getElementById(`viral-copy-${clip.id}-${index}`);
      if (btn) {
        btn.innerText = '已复制';
        setTimeout(() => { btn.innerText = '复制'; }, 1500);
      }
    });
  };

  const handleGenerateCaptions = async () => {
    setIsGeneratingCaption(true);
    setCaptionError('');
    try {
      const result = await generateCaptionSuggestions(clip.id);
      setCaptionSuggestions(result.captions);
    } catch (err) {
      console.error('生成发布文案失败', err);
      setCaptionError('生成失败，请重试');
    } finally {
      setIsGeneratingCaption(false);
    }
  };

  const handleReplaceCaption = async (caption: string, index: number) => {
    if (replacingCaptionIndex !== null || caption === currentCaption) return;
    setReplacingCaptionIndex(index);
    setCaptionError('');
    try {
      const result = await updateClipCaption(clip.id, caption);
      setCurrentCaption(result.caption);
    } catch (err) {
      console.error('替换发布文案失败', err);
      setCaptionError('文案替换失败，请重试');
    } finally {
      setReplacingCaptionIndex(null);
    }
  };

  const handleReplaceTitle = async (title: string, index: number) => {
    if (replacingTitleIndex !== null || title === currentTitle) return;
    setReplacingTitleIndex(index);
    setGenError('');
    try {
      const result = await updateClipTitle(clip.id, title);
      setCurrentTitle(result.title);
    } catch (err) {
      console.error('替换切片标题失败', err);
      setGenError('标题替换失败，请重试');
    } finally {
      setReplacingTitleIndex(null);
    }
  };

  const handleGenerateGuide = async () => {
    setIsGeneratingGuide(true);
    setGuideError('');
    try {
      const result = await generateEditingGuide(clip.id);
      setEditingGuide(result.editing_guide);
      setShowGuide(true);
      setGuideModalOpen(true);
    } catch (err) {
      console.error('生成剪辑思路失败', err);
      setGuideError('生成失败，请重试');
    } finally {
      setIsGeneratingGuide(false);
    }
  };

  // 生成星级，最高 10 分
  const starsArray = Array(5).fill(0);
  const scoreTo5 = Math.round(clip.virality_score / 2);

  return (
    <div className="glass-card flex flex-col h-full overflow-hidden">
      {/* 顶部标识：优先展示时间 */}
      <div className="flex items-center justify-between border-b border-stone-200 bg-stone-50 px-4 py-3 font-medium">
        <div className="flex items-center gap-3 overflow-hidden">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-teal-200 bg-teal-50 text-xs text-teal-800">
            #{clip.clip_index}
          </span>
          <div className="flex items-center gap-2 overflow-hidden">
            <span className="truncate font-mono text-base font-semibold tracking-tight text-stone-900">
              {formatClipTime(displayRange.startTime)} → {formatClipTime(displayRange.endTime)}
            </span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(copyableTimeRange);
                const btn = document.getElementById(`time-top-btn-${clip.id}`);
                if (btn) { 
                  btn.innerHTML = '<svg class="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>'; 
                  setTimeout(() => { 
                    btn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>'; 
                  }, 1500); 
                }
              }}
              id={`time-top-btn-${clip.id}`}
              title="复制时间"
              className="shrink-0 rounded p-1 text-stone-400 transition-colors hover:bg-stone-200 hover:text-stone-900"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
            </button>
          </div>
        </div>
        <span className="ml-2 shrink-0 whitespace-nowrap rounded border border-stone-200 bg-white px-2 py-0.5 font-mono text-xs text-stone-600">
          {formatClipTime(clip.duration)}
        </span>
      </div>

      <div className="p-5 flex-1 flex flex-col">
        {/* 标题 */}
        <div className="mb-4">
          <h4 className="text-lg font-semibold leading-snug text-stone-900">{currentTitle}</h4>
        </div>

        {/* 数据面板 */}
        <div className="flex gap-4 mb-4">
          <div className="flex-1 rounded-lg border border-stone-200 bg-stone-50 p-3">
            <div className="mb-1 text-xs text-stone-400">内容分类</div>
            <div className="text-sm font-medium text-teal-800">{clip.clip_type}</div>
          </div>
          <div className="flex-1 rounded-lg border border-stone-200 bg-stone-50 p-3">
            <div className="mb-1 text-xs text-stone-400">内容潜力 (1-10)</div>
            <div className="flex items-center gap-1">
              <span className="mr-1 text-sm font-bold text-orange-700">{clip.virality_score}</span>
              <div className="flex gap-0.5">
                {starsArray.map((_, i) => (
                  <svg key={i} className={`h-3 w-3 ${i < scoreTo5 ? 'text-orange-500' : 'text-stone-200'}`} fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* 摘要 */}
        <div className="mb-4 flex-1">
          <p className="text-sm leading-relaxed text-stone-600">
            {clip.summary}
          </p>
        </div>

        {/* 推荐文案 */}
        <div className="relative mb-4 rounded-lg border border-stone-200 bg-[#faf9f6] p-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs text-stone-400">推荐发布文案</span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleGenerateCaptions}
                disabled={isGeneratingCaption}
                className="text-xs font-medium text-teal-700 transition-colors hover:text-teal-900 disabled:opacity-50"
              >
                {isGeneratingCaption ? '生成中…' : captionSuggestions ? '换一批' : '重新生成'}
              </button>
              <button
                id={`copy-btn-${clip.id}`}
                type="button"
                onClick={handleCopyCaption}
                className="text-xs text-stone-500 transition-colors hover:text-teal-800"
              >
                复制
              </button>
            </div>
          </div>
          <p className="text-xs italic text-stone-600">
            "{currentCaption}"
          </p>
          {captionSuggestions && (
            <div className="mt-3 divide-y divide-teal-100 overflow-hidden rounded-lg border border-teal-200 bg-white">
              {captionSuggestions.map((caption, index) => (
                <div key={`${index}-${caption}`} className="p-3">
                  <p className="text-xs leading-5 text-stone-600">{caption}</p>
                  <div className="mt-2 flex justify-end">
                    <button
                      type="button"
                      onClick={() => handleReplaceCaption(caption, index)}
                      disabled={replacingCaptionIndex !== null || caption === currentCaption}
                      className="rounded border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-800 transition-colors hover:bg-teal-100 disabled:cursor-default disabled:opacity-50"
                    >
                      {caption === currentCaption
                        ? '当前文案'
                        : replacingCaptionIndex === index
                          ? '替换中…'
                          : '选用此文案'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {captionError && (
            <p className="mt-2 text-center text-xs text-red-600">{captionError}</p>
          )}
        </div>

        {/* 🔥 爆款标题推荐区域 */}
        <div className="mb-4">
          {!showTitles ? (
            <button
              onClick={handleGenerateViralTitles}
              disabled={isGenerating}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-orange-200 bg-orange-50 py-2.5 text-sm font-medium text-orange-800 transition-colors hover:bg-orange-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isGenerating ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  正在生成标题建议...
                </>
              ) : (
                <>生成标题建议</>
              )}
            </button>
          ) : (
            <div className="overflow-hidden rounded-lg border border-orange-200 bg-orange-50/50">
              <div className="flex items-center justify-between border-b border-orange-100 px-4 py-2.5">
                <span className="text-xs font-medium text-orange-400 flex items-center gap-1.5">
                  标题建议
                </span>
                <button
                  onClick={handleGenerateViralTitles}
                  disabled={isGenerating}
                  className="text-xs text-slate-400 hover:text-orange-300 transition-colors flex items-center gap-1 disabled:opacity-50"
                >
                  {isGenerating ? (
                    <>
                      <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                      生成中
                    </>
                  ) : (
                    <>🔄 换一批</>
                  )}
                </button>
              </div>
              <div className="divide-y divide-orange-100">
                {viralTitles?.map((title, index) => (
                  <div
                    key={index}
                    className="group/title flex items-center justify-between px-4 py-2 transition-colors hover:bg-orange-50"
                  >
                    <span className="mr-3 flex-1 text-sm text-stone-700">
                      <span className="text-orange-400/60 text-xs mr-2 font-mono">{index + 1}.</span>
                      {title}
                    </span>
                    <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover/title:opacity-100">
                      <button
                        type="button"
                        onClick={() => handleReplaceTitle(title, index)}
                        disabled={replacingTitleIndex !== null || title === currentTitle}
                        className="rounded border border-orange-200 bg-white px-2 py-1 text-xs font-medium text-orange-800 transition-colors hover:bg-orange-100 disabled:cursor-default disabled:opacity-50"
                      >
                        {title === currentTitle
                          ? '当前标题'
                          : replacingTitleIndex === index
                            ? '替换中…'
                            : '替换'}
                      </button>
                      <button
                        id={`viral-copy-${clip.id}-${index}`}
                        type="button"
                        onClick={() => handleCopyTitle(title, index)}
                        className="rounded px-2 py-1 text-xs text-stone-500 transition-colors hover:bg-orange-100 hover:text-orange-800"
                      >
                        复制
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {genError && (
            <p className="text-xs text-red-400 mt-2 text-center">{genError}</p>
          )}
        </div>

        {/* 🎬 剪辑思路区域 */}
        <div className="mb-5">
          {!showGuide ? (
            <button
              onClick={handleGenerateGuide}
              disabled={isGeneratingGuide}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-teal-200 bg-teal-50 py-2.5 text-sm font-medium text-teal-800 transition-colors hover:bg-teal-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isGeneratingGuide ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  正在生成剪辑思路...
                </>
              ) : (
                <>生成剪辑思路</>
              )}
            </button>
          ) : (
            <button
              onClick={() => setGuideModalOpen(true)}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-teal-200 bg-teal-50 py-2.5 text-sm font-medium text-teal-800 transition-colors hover:bg-teal-100"
            >
              查看剪辑思路
              <span className="ml-1 text-xs text-teal-600">已生成</span>
            </button>
          )}
          {guideError && (
            <p className="text-xs text-red-400 mt-2 text-center">{guideError}</p>
          )}
        </div>

        {/* 剪辑思路弹窗 */}
        {editingGuide && (
          <EditingGuideModal
            guide={editingGuide}
            clipTitle={currentTitle}
            isOpen={guideModalOpen}
            onClose={() => setGuideModalOpen(false)}
            onRegenerate={handleGenerateGuide}
            isRegenerating={isGeneratingGuide}
          />
        )}

        {/* 操作区 */}
        <div className="space-y-2">
          {clip.download_url ? (
            <a 
              href={clip.download_url} 
              target="_blank" 
              rel="noreferrer"
              className="btn-primary flex w-full items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              下载切片
            </a>
          ) : (
            <button
              onClick={() => {
                navigator.clipboard.writeText(copyableTimeRange);
                const btn = document.getElementById(`bottom-copy-msg-${clip.id}`);
                if (btn) { 
                  btn.innerText = '已复制！去剪映中裁切'; 
                  setTimeout(() => { btn.innerText = '一键复制时间，去剪映中裁切'; }, 2000); 
                }
              }}
              className="btn-secondary flex w-full items-center justify-center gap-2 text-center"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <span id={`bottom-copy-msg-${clip.id}`}>一键复制时间，去剪映中裁切</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
