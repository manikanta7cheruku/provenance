import { request, type MessageResponse, type SessionResponse } from "./api";

const BASE = "/api/v1/auth";

export function getSession(signal?: AbortSignal): Promise<SessionResponse> {
  return request<SessionResponse>("GET", `${BASE}/session`, { signal });
}

export function login(email: string, password: string): Promise<SessionResponse> {
  return request<SessionResponse>("POST", `${BASE}/login`, { body: { email, password } });
}

export function register(
  email: string,
  password: string,
  inviteCode: string | null,
): Promise<SessionResponse> {
  return request<SessionResponse>("POST", `${BASE}/register`, {
    body: { email, password, invite_code: inviteCode },
  });
}

export function logout(): Promise<SessionResponse> {
  return request<SessionResponse>("POST", `${BASE}/logout`);
}

export function forgotPassword(email: string): Promise<MessageResponse> {
  return request<MessageResponse>("POST", `${BASE}/password/forgot`, { body: { email } });
}

export function resetPassword(token: string, newPassword: string): Promise<MessageResponse> {
  return request<MessageResponse>("POST", `${BASE}/password/reset`, {
    body: { token, new_password: newPassword },
  });
}

export function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<SessionResponse> {
  return request<SessionResponse>("POST", `${BASE}/password/change`, {
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

export function confirmEmail(token: string): Promise<MessageResponse> {
  return request<MessageResponse>("POST", `${BASE}/email/verify/confirm`, { body: { token } });
}

export function requestVerification(): Promise<MessageResponse> {
  return request<MessageResponse>("POST", `${BASE}/email/verify/request`);
}
