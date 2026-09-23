import { api } from "./client";
import type { AuthTokens, RegisterResponse, User } from "../types";

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}

export const authApi = {
  async register(payload: RegisterPayload): Promise<RegisterResponse> {
    const { data } = await api.post<RegisterResponse>("/auth/register/", payload);
    return data;
  },
  async login(username: string, password: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>("/auth/login/", { username, password });
    return data;
  },
  async me(): Promise<User> {
    const { data } = await api.get<User>("/auth/me/");
    return data;
  },
};
