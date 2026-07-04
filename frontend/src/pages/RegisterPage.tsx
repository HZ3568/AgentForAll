import { FormEvent, useState } from 'react';
import { registerUser } from '../api/auth';

interface RegisterPageProps {
  onRegistered: () => void;
  onLogin: () => void;
}

export function RegisterPage({ onRegistered, onLogin }: RegisterPageProps) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      await registerUser({ username, email, password });
      onRegistered();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <h1>Create Account</h1>
        <p>Set up a Web user for isolated conversations.</p>
        <form onSubmit={handleSubmit}>
          <label>
            Username
            <input value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
          </label>
          <label>
            Password
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              minLength={8}
              required
            />
          </label>
          {error && <div className="error">{error}</div>}
          <button type="submit">Register</button>
        </form>
        <button className="link-button" onClick={onLogin} type="button">
          Back to login
        </button>
      </section>
    </main>
  );
}
