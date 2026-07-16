import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/AppLayout';
import Dashboard from './pages/Dashboard';
import GanttPage from './pages/GanttPage';
import TimelinePage from './pages/TimelinePage';

const App: React.FC = () => (
  <ConfigProvider locale={zhCN}>
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/gantt" element={<GanttPage />} />
          <Route path="/timeline" element={<TimelinePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </ConfigProvider>
);

export default App;
