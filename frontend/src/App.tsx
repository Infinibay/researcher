import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useWebSocketSync } from './hooks/useWebSocketSync'
import { useActivityFeedStore } from './stores/activityFeed'
import { Sidebar } from './components/layout/Sidebar'
import { Header } from './components/layout/Header'
import { Dashboard } from './components/pages/Dashboard'
import { ProjectsPage } from './components/pages/ProjectsPage'
import { EpicsPage } from './components/pages/EpicsPage'
import { TasksPage } from './components/pages/TasksPage'
import { ChatPage } from './components/pages/ChatPage'
import { WikiPage } from './components/pages/WikiPage'
import { FilesPage } from './components/pages/FilesPage'
import { RepositoriesPage } from './components/pages/RepositoriesPage'
import { FlowPage } from './components/pages/FlowPage'
import { AgentsPage } from './components/pages/AgentsPage'
import { ActivityFeed } from './components/chat/ActivityFeed'

export default function App() {
  useWebSocketSync()
  const feedOpen = useActivityFeedStore((s) => s.feedOpen)

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Header />
          <div className="flex flex-1 overflow-hidden">
            <main className="flex-1 overflow-auto p-6">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/epics" element={<EpicsPage />} />
                <Route path="/tasks" element={<TasksPage />} />
                <Route path="/agents" element={<AgentsPage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/wiki" element={<WikiPage />} />
                <Route path="/files" element={<FilesPage />} />
                <Route path="/repositories" element={<RepositoriesPage />} />
                <Route path="/flow" element={<FlowPage />} />
                <Route path="*" element={<Navigate to="/" />} />
              </Routes>
            </main>
            {feedOpen && (
              <aside className="w-80 shrink-0 border-l border-surface-700 overflow-hidden">
                <ActivityFeed />
              </aside>
            )}
          </div>
        </div>
      </div>
    </BrowserRouter>
  )
}
