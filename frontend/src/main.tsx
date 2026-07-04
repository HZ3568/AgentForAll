import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { getCurrentUser } from './api/auth';
import type { User } from './types/auth';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ChatPage } from './pages/ChatPage';
import './styles.css';

type View = 'login' | 'register' | 'chat';

function App() {
  const [view, setView] = useState<View>(localStorage.getItem('access_token') ? 'chat' : 'login');
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (view !== 'chat') {
      return;
    }
    getCurrentUser()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem('access_token');
        setUser(null);
        setView('login');
      });
  }, [view]);

  if (view === 'register') {
    return <RegisterPage onRegistered={() => setView('login')} onLogin={() => setView('login')} />;
  }

  if (view === 'chat') {
    return (
      <ChatPage
        user={user}
        onLogout={() => {
          localStorage.removeItem('access_token');
          setUser(null);
          setView('login');
        }}
      />
    );
  }

  return <LoginPage onLoggedIn={() => setView('chat')} onRegister={() => setView('register')} />;
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
