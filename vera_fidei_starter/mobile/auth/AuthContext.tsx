import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { AppState } from 'react-native'

import {
  getCurrentUser,
  loginUser,
  notifyLogout,
  registerUser,
  setAuthToken,
  setUnauthorizedHandler,
  type SessionUser,
} from '../lib/api'
import { deleteSecureToken, readSecureToken, saveSecureToken } from '../lib/secure-token'

type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

type AuthContextValue = {
  status: AuthStatus
  user: SessionUser | null
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<SessionUser | null>(null)

  const clearSession = useCallback(async () => {
    setAuthToken(null)
    setUser(null)
    try {
      await deleteSecureToken()
    } catch {
      // A sessão em memória precisa terminar mesmo se o Keystore foi invalidado.
    } finally {
      setStatus('anonymous')
    }
  }, [])

  const establishSession = useCallback(async (token: string, signal?: AbortSignal) => {
    setAuthToken(token)
    try {
      const profile = await getCurrentUser(signal)
      await saveSecureToken(token)
      setUser(profile)
      setStatus('authenticated')
    } catch (error) {
      setAuthToken(null)
      setUser(null)
      try {
        await deleteSecureToken()
      } catch {
        // O erro original da autenticação continua sendo a causa relevante.
      }
      throw error
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    async function restore() {
      try {
        const token = await readSecureToken()
        if (!token) {
          setStatus('anonymous')
          return
        }
        await establishSession(token, controller.signal)
      } catch {
        if (!controller.signal.aborted) await clearSession()
      }
    }
    void restore()
    return () => controller.abort()
  }, [clearSession, establishSession])

  useEffect(() => {
    setUnauthorizedHandler(() => void clearSession())
    return () => setUnauthorizedHandler(null)
  }, [clearSession])

  useEffect(() => {
    if (status !== 'authenticated') return
    let mounted = true
    const subscription = AppState.addEventListener('change', nextState => {
      if (nextState !== 'active') return
      void getCurrentUser()
        .then(profile => {
          if (mounted) setUser(profile)
        })
        .catch(() => {
          // A resposta 401 dispara o encerramento global da sessão.
        })
    })
    return () => {
      mounted = false
      subscription.remove()
    }
  }, [status])

  const login = useCallback(async (email: string, password: string) => {
    const token = await loginUser(email.trim().toLowerCase(), password)
    await establishSession(token)
  }, [establishSession])

  const register = useCallback(async (name: string, email: string, password: string) => {
    const token = await registerUser(name.trim(), email.trim().toLowerCase(), password)
    await establishSession(token)
  }, [establishSession])

  const logout = useCallback(async () => {
    await notifyLogout()
    await clearSession()
  }, [clearSession])

  const refreshUser = useCallback(async () => {
    const profile = await getCurrentUser()
    setUser(profile)
  }, [])

  const value = useMemo<AuthContextValue>(() => ({
    status,
    user,
    login,
    register,
    logout,
    refreshUser,
  }), [status, user, login, register, logout, refreshUser])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth precisa ser usado dentro de AuthProvider.')
  return value
}
