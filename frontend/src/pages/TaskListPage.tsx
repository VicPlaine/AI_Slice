import { useEffect, useEffectEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import TaskCard from '../components/TaskCard';
import type { TaskListItemProps } from '../components/TaskCard';
import { deleteTask, getTasks } from '../services/api';
import { shouldPollTaskList } from '../utils/taskPolling';

export default function TaskListPage() {
  const [tasks, setTasks] = useState<TaskListItemProps[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [taskToDelete, setTaskToDelete] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const hasProcessingTasks = shouldPollTaskList(tasks);

  const confirmDelete = async () => {
    if (!taskToDelete) return;
    setIsDeleting(true);
    try {
      await deleteTask(taskToDelete);
      setTasks((currentTasks) => currentTasks.filter((task) => task.id !== taskToDelete));
      setTaskToDelete(null);
    } catch (err) {
      console.error('Failed to delete task:', err);
      // fallback to a simple alert if it really fails
      alert('删除失败，请稍后重试');
    } finally {
      setIsDeleting(false);
    }
  };

  const fetchTasks = useEffectEvent(async (showLoadingSpinner: boolean) => {
    try {
      if (showLoadingSpinner) {
        setLoading(true);
      }
      setError('');
      const data = await getTasks();
      setTasks(data);
    } catch (err) {
      console.error('Failed to fetch tasks:', err);
      setError('加载任务列表失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  });

  useEffect(() => {
    void fetchTasks(true);
  }, []);

  useEffect(() => {
    if (hasProcessingTasks) {
      const timer = setInterval(() => {
        void fetchTasks(false);
      }, 3000);
      return () => clearInterval(timer);
    }
  }, [hasProcessingTasks]);

  return (
    <div className="mx-auto max-w-5xl pt-4">
      <div className="mb-8 flex items-end justify-between border-b border-stone-300 pb-7">
        <div>
          <p className="eyebrow mb-2">Project archive</p>
          <h2 className="text-4xl font-semibold tracking-tight text-stone-900">任务记录</h2>
          <p className="mt-2 text-sm text-stone-500">查看处理进度、切片方案与导出记录</p>
        </div>
        <Link to="/upload" className="btn-primary flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          新建项目
        </Link>
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-20">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-stone-300 border-t-teal-700"></div>
        </div>
      ) : error ? (
        <div className="glass-card border-red-200 bg-red-50 p-8 text-center text-red-700">
          <p>{error}</p>
        </div>
      ) : tasks.length === 0 ? (
        <div className="glass-card p-16 text-center">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-stone-100">
            <svg className="h-8 w-8 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <h3 className="text-xl font-semibold mb-2">暂无历史记录</h3>
          <p className="mb-6 text-stone-500">你还没有创建过切片任务</p>
          <Link to="/upload" className="btn-secondary">去创建第一个任务</Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {tasks.map(task => (
            <TaskCard 
              key={task.id} 
              task={task} 
              onDelete={(id, e) => {
                e.preventDefault();
                setTaskToDelete(id);
              }}
            />
          ))}
        </div>
      )}

      {/* 删除确认弹窗 */}
      {taskToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-opacity">
          <div className="w-full max-w-sm animate-in rounded-xl border border-stone-300 bg-white p-6 shadow-2xl duration-200 fade-in zoom-in-95">
            <h3 className="text-xl font-semibold mb-2">确认删除任务？</h3>
            <p className="mb-6 line-clamp-2 text-sm leading-relaxed text-stone-500">
              您确定要永久删除这个切片任务吗？此操作无法撤销。
            </p>
            <div className="flex gap-3 justify-end">
              <button 
                onClick={() => setTaskToDelete(null)}
                className="btn-secondary"
                disabled={isDeleting}
              >
                取消
              </button>
              <button 
                onClick={confirmDelete}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600/90 hover:bg-red-500 rounded-lg transition-colors flex items-center gap-2 shadow-lg shadow-red-500/20"
                disabled={isDeleting}
              >
                {isDeleting && (
                  <svg className="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                )}
                {isDeleting ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
