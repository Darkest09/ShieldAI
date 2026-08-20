import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { getMe, login as apiLogin, type SessionUser } from '@/api/client'

type AuthContextValue = {
  user: SessionUser | null
  loading: boolean
  login: (username: string, password: string, totpCode?: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!sessionStorage.getItem('shieldai_access_token')) {
      setLoading(false)
      return
    }
    void getMe()
      .then(setUser)
      .catch(() => sessionStorage.removeItem('shieldai_access_token'))
      .finally(() => setLoading(false))
  }, [])

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    async login(username, password, totpCode) {
      const result = await apiLogin(username, password, totpCode)
      sessionStorage.setItem('shieldai_access_token', result.access_token)
      setUser(await getMe())
    },
    logout() {
      sessionStorage.removeItem('shieldai_access_token')
      setUser(null)
    },
  }), [loading, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
