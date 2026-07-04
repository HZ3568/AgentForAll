import { FormEvent, useState } from 'react';
import { loginUser } from '../api/auth';

interface LoginPageProps {
  onLoggedIn: () => void;
  onRegister: () => void;
}

export function LoginPage({ onLoggedIn, onRegister }: LoginPageProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      await loginUser({ email, password });
      onLoggedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <h1>AgentForAll</h1>
        <p>Sign in to the Web workspace.</p>
        <form onSubmit={handleSubmit}>
          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
          </label>
          <label>
            Password
            <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" required />
          </label>
          {error && <div className="error">{error}</div>}
          <button type="submit">Login</button>
        </form>
        <button className="link-button" onClick={onRegister} type="button">
          Create an account
        </button>
      </section>
    </main>
  );
}
