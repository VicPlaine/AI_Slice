export type UploadFailureKind = 'cancelled' | 'timeout' | 'failed';

export interface UploadFailure {
  kind: UploadFailureKind;
  message: string;
}

export function classifyUploadFailure(error: unknown): UploadFailure {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return {
      kind: 'cancelled',
      message: '已取消当前处理',
    };
  }

  if (
    error &&
    typeof error === 'object' &&
    'code' in error &&
    (error as { code?: unknown }).code === 'ECONNABORTED'
  ) {
    return {
      kind: 'timeout',
      message: '上传超时，请检查网络后重试',
    };
  }

  if (error instanceof Error) {
    return {
      kind: 'failed',
      message: error.message,
    };
  }

  if (typeof error === 'string') {
    return {
      kind: 'failed',
      message: error,
    };
  }

  if (error && typeof error === 'object' && 'message' in error) {
    return {
      kind: 'failed',
      message: String((error as { message: unknown }).message),
    };
  }

  return {
    kind: 'failed',
    message: '处理过程中发生未知错误',
  };
}
