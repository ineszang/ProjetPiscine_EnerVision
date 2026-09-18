export type Role = 'lecteur' | 'operateur' | 'admin';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface Principal {
  id: string;
  email: string;
  role: Role;
  kind: 'human';
  must_change_password: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  principal: Principal;
}
