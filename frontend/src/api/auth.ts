import { apiRequest, setToken } from './client';
import type { LoginRequest, RegisterRequest, TokenResponse, User } from '../types/auth';

export async function registerUser(payload: RegisterRequest): Promise<User> {
  return apiRequest<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function loginUser(payload: LoginRequest): Promise<TokenResponse> {
  const token = await apiRequest<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  setToken(token.access_token);
  return token;
}

export async function getCurrentUser(): Promise<User> {
  return apiRequest<User>('/auth/me');
}
