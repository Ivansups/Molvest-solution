"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { authService } from "@/src/services/auth-service";
import type { NotificationItem, UserSession } from "@/src/types/domain";

interface AppContextValue {
  currentUser: UserSession | null;
  notifications: NotificationItem[];
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);
const AUTH_EVENT = "molvest-auth-change";

const defaultNotifications: NotificationItem[] = [];

function readStoredUser(): UserSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem("molvest-user");
  return raw ? (JSON.parse(raw) as UserSession) : null;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<UserSession | null>(() =>
    readStoredUser(),
  );

  useEffect(() => {
    const handleChange = () => setCurrentUser(readStoredUser());
    window.addEventListener("storage", handleChange);
    window.addEventListener(AUTH_EVENT, handleChange);
    return () => {
      window.removeEventListener("storage", handleChange);
      window.removeEventListener(AUTH_EVENT, handleChange);
    };
  }, []);

  const login = async (email: string, password: string) => {
    const user = await authService.login(email, password);
    window.localStorage.setItem("molvest-user", JSON.stringify(user));
    setCurrentUser(user);
    window.dispatchEvent(new Event(AUTH_EVENT));
  };

  const logout = () => {
    window.localStorage.removeItem("molvest-user");
    setCurrentUser(null);
    window.dispatchEvent(new Event(AUTH_EVENT));
  };

  return (
    <AppContext.Provider
      value={{
        currentUser,
        notifications: defaultNotifications,
        login,
        logout,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within AppProvider");
  }
  return context;
}
