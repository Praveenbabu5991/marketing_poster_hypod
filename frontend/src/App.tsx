import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { BrandSetup } from './pages/BrandSetup';
import { Chat } from './pages/Chat';
import { Calendar } from './pages/Calendar';
import { Usage } from './pages/Usage';
import { Admin } from './pages/Admin';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="brands/new" element={<BrandSetup />} />
          <Route path="brands/:id/edit" element={<BrandSetup />} />
          <Route path="chat/:sessionId" element={<Chat />} />
          <Route path="calendar" element={<Calendar />} />
          <Route path="usage" element={<Usage />} />
          <Route path="admin" element={<Admin />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
