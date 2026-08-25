import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FileUploader from '../components/FileUploader';
import { createTask } from '../services/api';
import { SCENE_MODE_OPTIONS } from '../types/task';
import type { SceneMode } from '../types/task';

type Status = 'idle' | 'extracting' | 'uploading' | 'processing' | 'error';

export default function UploadPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<Status>('idle');
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [noticeMessage, setNoticeMessage] = useState('');
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [cancelUpload, setCancelUpload] = useState<(() => void) | null>(null);
  const [sceneMode, setSceneMode] = useState<SceneMode>('livestream');

  const handleUploadStart = () => {
    setStatus('extracting');
    setProgress(0);
    setProgressMessage('准备中...');
    setErrorMessage('');
    setNoticeMessage('');
  };

  const handleExtractProgress = (p: number, message: string) => {
    setStatus('extracting');
    setProgress(p);
    setProgressMessage(message);
  };

  const handleUploadProgress = (p: number) => {
    setStatus('uploading');
    setProgress(p);
    setProgressMessage('正在上传音频...');
  };

  const handleUploadSuccess = async (
    file: File,
    audioPath: string,
    startOffset: number,
    videoDuration: number | null,
  ) => {
    setStatus('processing');
    setProgress(95);
    setProgressMessage('上传完成，正在创建任务...');
    setCurrentFile(file);
    
    try {
      const task = await createTask({
        video_filename: file.name,
        video_path: audioPath,
        video_start_offset: startOffset || 0,
        video_duration: videoDuration ?? undefined,
        scene_mode: sceneMode,
      });
      
      navigate(`/tasks/${task.id}`);
    } catch (error) {
      console.error('任务创建失败:', error);
      setStatus('error');
      setErrorMessage(error instanceof Error ? error.message : '创建处理任务失败');
    }
  };

  const handleUploadError = (error: Error) => {
    setStatus('error');
    setErrorMessage(error.message);
    setCancelUpload(null);
  };

  const handleUploadCancelled = (message: string) => {
    setStatus('idle');
    setProgress(0);
    setProgressMessage('');
    setErrorMessage('');
    setCurrentFile(null);
    setCancelUpload(null);
    setNoticeMessage(message);
  };

  const handleCancelChange = (cancel: (() => void) | null) => {
    setCancelUpload(() => cancel);
  };

  const getStatusLabel = () => {
    switch (status) {
      case 'extracting': return '正在提取音频';
      case 'uploading': return '正在上传音频';
      case 'processing': return '准备分析';
      default: return '';
    }
  };

  const getStatusDescription = () => {
    if (progressMessage) return progressMessage;
    switch (status) {
      case 'extracting':
        return `浏览器端解析视频中，无需上传完整文件... ${currentFile?.name || ''}`;
      case 'uploading':
        return '音频已提取，正在上传至服务器...';
      case 'processing':
        return '上传完成，正在初始化千问分析服务...';
      default:
        return '';
    }
  };

  const selectedScene = SCENE_MODE_OPTIONS.find(o => o.value === sceneMode)!;

  return (
    <div className="mx-auto max-w-4xl pt-4">
      <div className="mb-10 border-b border-stone-300 pb-8">
        <p className="eyebrow mb-3">New clipping project</p>
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <h2 className="max-w-2xl text-4xl font-semibold leading-tight tracking-[-0.035em] text-stone-900 md:text-5xl">
            把长视频，整理成<br />可以直接发布的片段
          </h2>
          <p className="max-w-xs text-sm leading-6 text-stone-500">
            视频留在本机，只上传提取后的音频。千问负责识别内容并给出剪辑时间点。
          </p>
        </div>
      </div>

      {/* ── 场景模式选择器 ── */}
      {(status === 'idle' || status === 'error') && (
        <div className="mb-6">
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
            </svg>
            选择视频类型
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {SCENE_MODE_OPTIONS.map((option) => (
              <button
                key={option.value}
                id={`scene-mode-${option.value}`}
                onClick={() => setSceneMode(option.value)}
                className={`group relative overflow-hidden rounded-lg border p-4 text-left transition-all duration-200 ${
                  sceneMode === option.value
                    ? 'border-teal-700 bg-teal-50 shadow-sm'
                    : 'border-stone-300 bg-white hover:border-stone-500'
                }`}
              >
                {/* 选中指示器 */}
                {sceneMode === option.value && (
                  <div className="absolute right-2.5 top-2.5 flex h-5 w-5 items-center justify-center rounded-full bg-teal-700">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
                <span className="mb-2 block text-xl">{option.icon}</span>
                <h4 className={`mb-1 text-sm font-semibold ${
                  sceneMode === option.value ? 'text-teal-900' : 'text-stone-800'
                }`}>
                  {option.label}
                </h4>
                <p className="text-xs leading-relaxed text-stone-500">{option.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="glass-card mt-5 p-3">
        <div className="relative flex min-h-[380px] flex-col justify-center overflow-hidden rounded-lg bg-[#faf9f6] p-6 sm:p-8">
          
          {status === 'idle' || status === 'error' ? (
            <div className="z-10 relative">
              <FileUploader 
                onUploadStart={handleUploadStart}
                onExtractProgress={handleExtractProgress}
                onUploadProgress={handleUploadProgress}
                onUploadSuccess={handleUploadSuccess}
                onUploadError={handleUploadError}
                onUploadCancelled={handleUploadCancelled}
                onCancelChange={handleCancelChange}
              />

              {status === 'idle' && noticeMessage && (
                <div className="mt-6 flex items-start gap-3 rounded-lg border border-stone-300 bg-white p-4 text-stone-700">
                  <svg className="mt-0.5 h-5 w-5 shrink-0 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div>
                    <h4 className="font-semibold">已停止当前处理</h4>
                    <p className="text-sm mt-1">{noticeMessage}</p>
                  </div>
                </div>
              )}
              
              {status === 'error' && (
                <div className="mt-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
                  <svg className="w-5 h-5 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div>
                    <h4 className="font-semibold">处理出错</h4>
                    <p className="text-sm mt-1">{errorMessage}</p>
                    <button 
                      onClick={() => setStatus('idle')}
                      className="mt-3 text-sm text-red-700 underline underline-offset-2 hover:text-red-900"
                    >
                      重新尝试
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="z-10 flex flex-col items-center justify-center py-12">
              <div className="relative w-32 h-32 mb-8">
                {/* 环形进度条背景 */}
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="8" className="text-stone-200" />
                  <circle 
                    cx="50" cy="50" r="45" 
                    fill="none" 
                    stroke="currentColor" 
                    strokeWidth="8" 
                    strokeLinecap="round"
                    className={`${status === 'extracting' ? 'text-orange-600' : 'text-teal-700'} transition-all duration-500`}
                    strokeDasharray="283"
                    strokeDashoffset={283 - (283 * progress) / 100}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center flex-col">
                  <span className={`text-3xl font-semibold ${status === 'extracting' ? 'text-orange-700' : 'text-teal-800'}`}>
                    {progress}%
                  </span>
                </div>
              </div>
              
              {/* 场景标签 */}
              <div className="mb-4 flex items-center gap-1.5 rounded-full border border-stone-300 bg-white px-3 py-1 text-xs text-stone-500">
                <span>{selectedScene.icon}</span>
                <span>{selectedScene.label}模式</span>
              </div>

              {/* 阶段指示器 */}
              <div className="flex items-center gap-3 mb-4">
                {['extracting', 'uploading', 'processing'].map((step, i) => (
                  <div key={step} className="flex items-center gap-2">
                    <div className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
                      status === step 
                        ? 'bg-teal-700 ring-4 ring-teal-700/15'
                        : ['extracting', 'uploading', 'processing'].indexOf(status) > i
                          ? 'bg-emerald-500'
                          : 'bg-stone-300'
                    }`} />
                    {i < 2 && <div className={`w-8 h-0.5 ${
                      ['extracting', 'uploading', 'processing'].indexOf(status) > i ? 'bg-teal-600/50' : 'bg-stone-300'
                    }`} />}
                  </div>
                ))}
              </div>
              <div className="mb-6 flex w-48 justify-between text-xs text-stone-400">
                <span className={status === 'extracting' ? 'text-orange-700' : ''}>提取</span>
                <span className={status === 'uploading' ? 'text-teal-700' : ''}>上传</span>
                <span className={status === 'processing' ? 'text-teal-700' : ''}>分析</span>
              </div>

              <h3 className="text-xl font-semibold mb-2">
                {getStatusLabel()}
              </h3>
              <p className="max-w-sm text-center text-sm text-stone-500">
                {getStatusDescription()}
              </p>
              {cancelUpload && status !== 'processing' && (
                <button
                  onClick={cancelUpload}
                  className="btn-secondary mt-6"
                >
                  取消当前处理
                </button>
              )}
            </div>
          )}
          
        </div>
      </div>

      {/* 步骤指引 */}
      <div className="mt-12 grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-stone-300 bg-stone-300 md:grid-cols-3">
        {[
          { num: '01', title: '选择场景', desc: '选择视频类型：直播回放找爆款、播客访谈提炼观点、课程讲座按知识点拆分' },
          { num: '02', title: '智能分析', desc: '千问语音识别 + 千问大模型，根据场景策略自动定位切片点' },
          { num: '03', title: '一键导出', desc: '系统整理精彩片段时间点与标题文案，支持本地 FFmpeg 切片和 ZIP 下载' }
        ].map((step) => (
          <div key={step.num} className="flex flex-col bg-white p-6">
            <span className="mb-6 font-mono text-xs font-semibold text-orange-700">STEP {step.num}</span>
            <h4 className="mb-2 text-base font-semibold text-stone-900">{step.title}</h4>
            <p className="text-sm leading-relaxed text-stone-500">{step.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

