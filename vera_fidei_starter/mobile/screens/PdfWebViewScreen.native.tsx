import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ActivityIndicator, AppState, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import * as WebBrowser from 'expo-web-browser'
import { WebView } from 'react-native-webview'

import { useAuth } from '../auth/AuthContext'
import { syncBillingSubscription } from '../lib/api'
import {
  allowsAccountWeb,
  allowsExternalBilling,
  isPdfNavigationAllowed,
} from '../lib/distribution-policy'
import { API_BASE, DISTRIBUTION_MODE, WEB_BASE } from '../lib/runtime-config'
import { readSecureToken } from '../lib/secure-token'
import { colors } from '../lib/theme'
import {
  buildMobileAccountRedirect,
  buildMobileAccountSessionUrl,
  buildMobileWebRedirect,
  buildMobileWebSessionUrl,
  isTrustedStripeNavigation,
} from '../lib/url'

function waitForRetry(delayMs: number, signal: AbortSignal): Promise<void> {
  return new Promise(resolve => {
    if (signal.aborted || delayMs <= 0) {
      resolve()
      return
    }
    const timeout = setTimeout(() => {
      signal.removeEventListener('abort', onAbort)
      resolve()
    }, delayMs)
    const onAbort = () => {
      clearTimeout(timeout)
      resolve()
    }
    signal.addEventListener('abort', onAbort, { once: true })
  })
}

export default function PdfWebViewScreen({ route, navigation }: { route: any; navigation: any }) {
  const fileId = Number(route.params?.fileId)
  const page = Number(route.params?.page ?? 1)
  const destination = route.params?.destination
  const isAccount = destination !== undefined
  const { logout, refreshUser } = useAuth()
  const [token, setToken] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const webViewRef = useRef<WebView>(null)
  const mountedRef = useRef(true)
  const appStateRef = useRef(AppState.currentState)
  const billingFlowRef = useRef<'checkout' | 'portal' | null>(null)
  const billingSyncRunningRef = useRef(false)
  const billingSyncControllerRef = useRef<AbortController | null>(null)

  const redirect = useMemo(() => {
    try {
      if (isAccount && !allowsAccountWeb(DISTRIBUTION_MODE, destination)) return null
      return isAccount
        ? buildMobileAccountRedirect(String(destination))
        : buildMobileWebRedirect(fileId, page)
    } catch {
      return null
    }
  }, [destination, fileId, isAccount, page])

  useEffect(() => {
    let mounted = true
    void readSecureToken()
      .then(value => {
        if (!mounted) return
        if (!value) {
          setError('Sua sessão nativa não está disponível. Entre novamente.')
          setLoading(false)
          return
        }
        setToken(value)
        setError('')
        setLoading(true)
      })
      .catch(() => {
        if (mounted) {
          setError('Não foi possível acessar a sessão segura do aparelho.')
          setLoading(false)
        }
      })
    return () => {
      mounted = false
    }
  }, [attempt])

  const source = useMemo(() => {
    if (!token || !redirect) return null
    return {
      uri: isAccount
        ? buildMobileAccountSessionUrl(API_BASE)
        : buildMobileWebSessionUrl(API_BASE),
      method: 'GET' as const,
      headers: {
        Accept: 'text/html,application/xhtml+xml',
        Authorization: `Bearer ${token}`,
        'X-Vera-Fidei-Redirect': redirect,
      },
    }
  }, [isAccount, redirect, token])

  const syncBillingAfterReturn = useCallback(async () => {
    const flow = billingFlowRef.current
    if (!flow || billingSyncRunningRef.current) return

    billingSyncRunningRef.current = true
    const controller = new AbortController()
    billingSyncControllerRef.current?.abort()
    billingSyncControllerRef.current = controller
    const overallTimeout = setTimeout(() => controller.abort(), 60_000)
    let synced = false

    try {
      for (const delay of [0, 2_000, 4_000, 8_000, 12_000]) {
        await waitForRetry(delay, controller.signal)
        if (controller.signal.aborted) break
        try {
          const result = await syncBillingSubscription(controller.signal)
          if (result.synced) {
            synced = true
            break
          }
        } catch {
          if (controller.signal.aborted) break
        }
      }

      if (!controller.signal.aborted) {
        try {
          await refreshUser()
        } catch {
          // O próximo retorno ao app repetirá a leitura da conta.
        }
        if (mountedRef.current && (synced || flow === 'portal')) {
          const returnPath = flow === 'checkout'
            ? '/perfil?assinatura=sucesso'
            : '/perfil?assinatura=portal'
          webViewRef.current?.injectJavaScript(
            `window.location.replace(${JSON.stringify(returnPath)}); true;`,
          )
        }
      }
    } finally {
      clearTimeout(overallTimeout)
      if (billingSyncControllerRef.current === controller) billingSyncControllerRef.current = null
      billingSyncRunningRef.current = false
      billingFlowRef.current = null
    }
  }, [refreshUser])

  useEffect(() => {
    const subscription = AppState.addEventListener('change', nextState => {
      const previousState = appStateRef.current
      appStateRef.current = nextState
      if (nextState === 'active' && previousState !== 'active' && billingFlowRef.current) {
        void syncBillingAfterReturn()
      }
    })
    return () => {
      mountedRef.current = false
      subscription.remove()
      billingSyncControllerRef.current?.abort()
      billingSyncControllerRef.current = null
    }
  }, [syncBillingAfterReturn])

  useEffect(() => {
    if (!source || !loading || error) return undefined

    const timeout = setTimeout(() => {
      webViewRef.current?.stopLoading()
      setLoading(false)
      setError(`${isAccount ? 'A página' : 'O PDF'} demorou demais para abrir. Verifique sua conexão e tente novamente.`)
    }, 45_000)

    return () => clearTimeout(timeout)
  }, [attempt, error, isAccount, loading, source])

  if (!redirect) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{isAccount ? 'Destino da conta inválido.' : 'Arquivo ou página inválidos.'}</Text>
        <TouchableOpacity style={styles.button} onPress={() => navigation.goBack()}><Text style={styles.buttonText}>Voltar</Text></TouchableOpacity>
      </View>
    )
  }

  if (error || !source) {
    return (
      <View style={styles.center}>
        {loading ? <ActivityIndicator size="large" color={colors.gold} /> : null}
        {error ? <Text style={styles.error}>{error}</Text> : <Text style={styles.help}>Preparando sessão segura…</Text>}
        {error ? (
          <TouchableOpacity style={styles.button} onPress={() => setAttempt(value => value + 1)}><Text style={styles.buttonText}>Tentar novamente</Text></TouchableOpacity>
        ) : null}
        <TouchableOpacity style={styles.button} onPress={() => navigation.goBack()}><Text style={styles.buttonText}>Voltar</Text></TouchableOpacity>
      </View>
    )
  }

  return (
    <View style={styles.root}>
      <WebView
        ref={webViewRef}
        key={`${redirect}:${attempt}`}
        source={source}
        incognito
        cacheEnabled={false}
        cacheMode="LOAD_NO_CACHE"
        sharedCookiesEnabled={false}
        thirdPartyCookiesEnabled={false}
        mixedContentMode="never"
        allowFileAccess={false}
        allowFileAccessFromFileURLs={false}
        allowUniversalAccessFromFileURLs={false}
        javaScriptCanOpenWindowsAutomatically={false}
        setSupportMultipleWindows={false}
        allowsLinkPreview={false}
        startInLoadingState
        onLoadStart={() => setLoading(true)}
        onLoadEnd={() => setLoading(false)}
        onShouldStartLoadWithRequest={request => {
          const trustedNavigation = isPdfNavigationAllowed(DISTRIBUTION_MODE, request.url, WEB_BASE)
          if (trustedNavigation) return true
          if (
            isAccount
            && allowsExternalBilling(DISTRIBUTION_MODE)
            && isTrustedStripeNavigation(request.url)
          ) {
            if (request.isTopFrame !== false && !billingFlowRef.current) {
              billingFlowRef.current = new URL(request.url).hostname === 'checkout.stripe.com'
                ? 'checkout'
                : 'portal'
              setLoading(false)
              void WebBrowser.openBrowserAsync(request.url, {
                controlsColor: colors.gold,
                presentationStyle: WebBrowser.WebBrowserPresentationStyle.FULL_SCREEN,
              })
                .then(result => {
                  if (result.type !== WebBrowser.WebBrowserResultType.OPENED) {
                    void syncBillingAfterReturn()
                  }
                })
                .catch(() => {
                  billingFlowRef.current = null
                  if (mountedRef.current) setError('Não foi possível abrir a página segura de pagamento.')
                })
            }
            return false
          }
          setError(`A ${isAccount ? 'página da conta' : 'visualização'} bloqueou uma navegação para fora do Vera Fidei.`)
          return false
        }}
        onHttpError={event => {
          const statusCode = event.nativeEvent.statusCode
          if (statusCode === 401) {
            setError('Sua sessão expirou. Entre novamente.')
            void logout()
          } else if (statusCode === 403) {
            setError(
              isAccount
                ? 'Sua conta não tem acesso a esta página.'
                : DISTRIBUTION_MODE !== 'direct'
                  ? 'A leitura do PDF digitalizado requer uma assinatura ativa com acesso a este recurso.'
                  : 'O PDF completo requer o plano Apologeta ou superior.',
            )
          } else {
            setError(`O visualizador respondeu com erro ${statusCode}.`)
          }
          setLoading(false)
        }}
        onError={() => {
          setError(`Não foi possível carregar ${isAccount ? 'a página' : 'o PDF'}. Verifique sua conexão.`)
          setLoading(false)
        }}
      />
      {loading ? (
        <View pointerEvents="none" style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color={colors.gold} />
          <Text style={styles.help}>Abrindo {isAccount ? 'a página da conta' : 'o PDF'} com sessão segura…</Text>
        </View>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24 },
  loadingOverlay: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, alignItems: 'center', justifyContent: 'center', gap: 12, backgroundColor: colors.background },
  help: { color: colors.muted, textAlign: 'center' },
  error: { color: '#fecaca', textAlign: 'center', lineHeight: 20 },
  button: { minWidth: 150, alignItems: 'center', borderWidth: 1, borderColor: '#6b5721', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10 },
  buttonText: { color: colors.gold, fontWeight: '900' },
})
