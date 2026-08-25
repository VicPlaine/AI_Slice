import { Routes, Route, Navigate, Link, NavLink } from 'react-router-dom'

import UploadPage from './pages/UploadPage'
import TaskListPage from './pages/TaskListPage'
import TaskDetailPage from './pages/TaskDetailPage'

function App() {
  return (
    <div className="app-shell min-h-screen flex flex-col">
      <header className="app-header sticky top-0 z-20 w-full">
        <Link to="/upload" className="flex items-center gap-3">
          <div className="brand-mark" aria-hidden="true">S</div>
          <div>
            <h1 className="text-[17px] font-semibold leading-none tracking-tight text-stone-900">Slice Studio</h1>
            <p className="mt-1 text-[10px] font-medium uppercase tracking-[0.2em] text-stone-400">Content workspace</p>
          </div>
        </Link>
        <nav className="flex items-center gap-1 rounded-lg bg-stone-100 p-1">
          <NavLink to="/upload" className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}>新建项目</NavLink>
          <NavLink to="/tasks" className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}>任务记录</NavLink>
        </nav>
      </header>

      <main className="flex-1 w-full max-w-6xl mx-auto px-5 py-8 sm:px-8 sm:py-10">
        <Routes>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/tasks" element={<TaskListPage />} />
          <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App

