import { type PropsWithChildren, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AppState, Platform } from 'react-native'
import {
  deepLinkToSubscriptions,
  ErrorCode,
  getAvailablePurchases,
  type ProductSubscription,
  type Purchase,
  useIAP,
} from 'expo-iap'

import { useAuth } from '../auth/AuthContext'
import {
  getGooglePlayBillingCatalog,
  getGooglePlayBillingStatus,
  syncGooglePlaySubscriptions,
} from '../lib/api'
import { allowsPlayBilling } from '../lib/distribution-policy'
import {
  blocksPlayPurchaseForExternalBilling,
  finishablePurchaseIndexes,
  PAID_PLAN_KEYS,
  PLAY_PLAN_DETAILS,
  playOfferTerms,
  playPurchasePreflightBillingState,
  playSyncOutcome,
  replacementModeForPlans,
  selectPlayOffer,
  type PaidPlanKey,
  type PlayBillingCatalog,
} from '../lib/play-billing'
import { DISTRIBUTION_MODE } from '../lib/runtime-config'
import { PlayBillingContext, type PlayBillingContextValue } from './PlayBillingContext'

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim() ? error.message : fallback
}

function isUserCancellation(error: { code?: ErrorCode | string }): boolean {
  return error.code === ErrorCode.UserCancelled
}

export default function PlayBillingProvider({ children }: PropsWithChildren) {
  const { user, refreshUser } = useAuth()
  const enabledForBuild = allowsPlayBilling(DISTRIBUTION_MODE, Platform.OS)
  const [catalog, setCatalog] = useState<PlayBillingCatalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [operation, setOperation] = useState<'purchase' | 'restore' | 'sync' | null>(null)
  const [processingProductId, setProcessingProductId] = useState<string | null>(null)
  const [activeProductId, setActiveProductId] = useState<string | null>(null)
  const [billingStatus, setBillingStatus] = useState<string | null>(null)
  const [billingStateVerified, setBillingStateVerified] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const mountedRef = useRef(true)
  const purchaseHandlerRef = useRef<(purchase: Purchase) => void>(() => undefined)
  const initialSyncKeyRef = useRef('')
  const reconcileQueueRef = useRef<Promise<void>>(Promise.resolve())

  const {
    connected,
    subscriptions,
    fetchProducts,
    finishTransaction,
    reconnect,
    requestPurchase,
  } = useIAP({
    onPurchaseSuccess: purchase => purchaseHandlerRef.current(purchase),
    onPurchaseError: purchaseError => {
      if (!mountedRef.current) return
      setProcessingProductId(null)
      setOperation(null)
      if (isUserCancellation(purchaseError)) {
        setNotice('Compra cancelada. Nenhuma cobrança foi concluída.')
        return
      }
      setError(purchaseError.message || 'O Google Play não conseguiu concluir a compra.')
    },
    onError: generalError => {
      if (mountedRef.current) setError(errorMessage(generalError, 'A cobrança do Google Play está indisponível.'))
    },
  })

  const loadBackendState = useCallback(async () => {
    if (!enabledForBuild) {
      if (mountedRef.current) {
        setCatalog(null)
        setLoading(false)
        setError('Esta instalação não permite compras pelo Google Play.')
      }
      return
    }

    if (mountedRef.current) {
      setLoading(true)
      setError('')
      setBillingStateVerified(false)
    }
    try {
      const nextCatalog = await getGooglePlayBillingCatalog()
      if (!mountedRef.current) return
      setCatalog(nextCatalog)
      if (!nextCatalog.enabled) {
        setError('Os planos do Google Play ainda não estão disponíveis para esta conta.')
      }
    } catch (reason) {
      if (!mountedRef.current) return
      setCatalog(null)
      setError(errorMessage(reason, 'Não foi possível carregar os planos do Google Play.'))
    }

    try {
      const status = await getGooglePlayBillingStatus()
      if (mountedRef.current) {
        setActiveProductId(status.active_product_id)
        setBillingStatus(status.billing_status)
        setBillingStateVerified(true)
      }
    } catch {
      if (mountedRef.current) {
        setBillingStateVerified(false)
        setError(current => current || 'Não foi possível confirmar a situação atual da assinatura. Tente novamente.')
      }
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [enabledForBuild])

  useEffect(() => {
    mountedRef.current = true
    const timer = setTimeout(() => void loadBackendState(), 0)
    return () => {
      clearTimeout(timer)
      mountedRef.current = false
    }
  }, [loadBackendState, user?.id])

  useEffect(() => {
    if (!catalog?.enabled || !connected) return
    const productIds = catalog.products.map(product => product.product_id)
    if (productIds.length === 0) return
    const timer = setTimeout(() => {
      setLoading(true)
      void fetchProducts({ skus: productIds, type: 'subs' })
        .catch(reason => {
          if (mountedRef.current) setError(errorMessage(reason, 'O Google Play não retornou os planos disponíveis.'))
        })
        .finally(() => {
          if (mountedRef.current) setLoading(false)
        })
    }, 0)
    return () => clearTimeout(timer)
  }, [catalog, connected, fetchProducts])

  const reconcilePurchases = useCallback(async (
    purchases: Purchase[],
    requestedOperation: 'sync' | 'restore',
    interactive: boolean,
  ) => {
    const currentCatalog = catalog
    if (!currentCatalog?.enabled) {
      if (interactive && mountedRef.current) setError('A validação de compras ainda não está disponível.')
      return
    }
    const allowedProducts = new Set(currentCatalog.products.map(product => product.product_id))
    const seenTokens = new Set<string>()
    const localPurchases = purchases.filter(purchase => {
      const token = purchase.purchaseToken?.trim()
      if (!token || seenTokens.has(token) || !allowedProducts.has(purchase.productId)) return false
      seenTokens.add(token)
      return true
    })

    if (localPurchases.length === 0) {
      if (interactive && mountedRef.current) {
        setNotice(requestedOperation === 'restore'
          ? 'Nenhuma assinatura do Vera Fidei foi encontrada nesta conta do Google Play.'
          : 'Nenhuma compra pendente de sincronização foi encontrada.')
      }
      return
    }

    if (mountedRef.current) {
      setOperation(requestedOperation)
      setError('')
      if (interactive) setNotice('Conferindo a assinatura com o Google Play…')
    }
    try {
      const response = await syncGooglePlaySubscriptions(
        localPurchases.map(purchase => ({
          purchase_token: purchase.purchaseToken!.trim(),
          product_id: purchase.productId,
        })),
        requestedOperation,
      )

      for (const index of finishablePurchaseIndexes(response, localPurchases.length)) {
        await finishTransaction({ purchase: localPurchases[index], isConsumable: false })
      }

      if (mountedRef.current) {
        setActiveProductId(response.active_product_id)
        setBillingStatus(response.billing_status)
        const outcome = playSyncOutcome(response, requestedOperation)
        if (outcome.kind === 'error') setError(outcome.message)
        else setNotice(outcome.message)
      }

      try {
        await refreshUser()
      } catch {
        // A assinatura já foi tratada; o perfil será atualizado no próximo retorno ao app.
      }
      try {
        const status = await getGooglePlayBillingStatus()
        if (mountedRef.current) {
          setActiveProductId(status.active_product_id)
          setBillingStatus(status.billing_status)
          setBillingStateVerified(true)
        }
      } catch {
        // A resposta autoritativa da sincronização já foi aplicada acima.
      }
    } catch (reason) {
      if (mountedRef.current) {
        setError(errorMessage(reason, 'Não foi possível validar a compra. Ela não foi finalizada no aparelho.'))
      }
    } finally {
      if (mountedRef.current) {
        setOperation(null)
        setProcessingProductId(null)
      }
    }
  }, [catalog, finishTransaction, refreshUser])

  const enqueueReconciliation = useCallback((
    purchases: Purchase[],
    requestedOperation: 'sync' | 'restore',
    interactive: boolean,
  ): Promise<void> => {
    const task = reconcileQueueRef.current.then(() => reconcilePurchases(purchases, requestedOperation, interactive))
    reconcileQueueRef.current = task.catch(() => undefined)
    return task
  }, [reconcilePurchases])

  useEffect(() => {
    purchaseHandlerRef.current = purchase => {
      if (!enabledForBuild) return
      if (purchase.purchaseState === 'pending' && mountedRef.current) {
        setNotice('Pagamento pendente. O plano não será liberado antes da confirmação do Google Play.')
      }
      void enqueueReconciliation([purchase], 'sync', true)
    }
    return () => {
      purchaseHandlerRef.current = () => undefined
    }
  }, [enabledForBuild, enqueueReconciliation])

  const queryAndReconcile = useCallback(async (
    requestedOperation: 'sync' | 'restore',
    interactive: boolean,
  ) => {
    if (!enabledForBuild || !catalog?.enabled || !connected) {
      if (interactive && mountedRef.current) {
        setError('O Google Play ainda não está conectado. Tente novamente em instantes.')
      }
      return
    }
    try {
      const purchases = await getAvailablePurchases({ includeSuspendedAndroid: true })
      await enqueueReconciliation(purchases, requestedOperation, interactive)
    } catch (reason) {
      if (mountedRef.current) setError(errorMessage(reason, 'Não foi possível consultar suas compras no Google Play.'))
    }
  }, [catalog, connected, enabledForBuild, enqueueReconciliation])

  useEffect(() => {
    if (!catalog?.enabled || !connected || !user?.id) return
    const key = `${user.id}:${catalog.products.map(product => product.product_id).sort().join(',')}`
    if (initialSyncKeyRef.current === key) return
    initialSyncKeyRef.current = key
    void queryAndReconcile('sync', false)
  }, [catalog, connected, queryAndReconcile, user?.id])

  useEffect(() => {
    if (!enabledForBuild) return
    let previousState = AppState.currentState
    const subscription = AppState.addEventListener('change', nextState => {
      const shouldSync = nextState === 'active' && previousState !== 'active'
      previousState = nextState
      if (shouldSync) void queryAndReconcile('sync', false)
    })
    return () => subscription.remove()
  }, [enabledForBuild, queryAndReconcile])

  const planViews = useMemo(() => PAID_PLAN_KEYS.map(plan => {
    const configured = catalog?.products.find(product => product.plan === plan) ?? null
    const storeProduct = configured
      ? subscriptions.find(product => product.id === configured.product_id && product.platform === 'android') as ProductSubscription | undefined
      : undefined
    const offer = storeProduct?.platform === 'android'
      ? selectPlayOffer(storeProduct.subscriptionOffers, configured?.base_plan_id ?? null)
      : null
    const storeAvailable = storeProduct?.platform === 'android'
      && (!storeProduct.productStatusAndroid || storeProduct.productStatusAndroid === 'ok')
      && Boolean(offer)
    return {
      plan,
      ...PLAY_PLAN_DETAILS[plan],
      productId: configured?.product_id ?? null,
      displayPrice: offer?.displayPrice || storeProduct?.displayPrice || 'Indisponível',
      offerTerms: playOfferTerms(offer),
      available: Boolean(enabledForBuild && catalog?.enabled && billingStateVerified && connected && storeAvailable),
      current: Boolean(configured?.product_id && configured.product_id === activeProductId),
    }
  }), [activeProductId, billingStateVerified, catalog, connected, enabledForBuild, subscriptions])

  const purchasePlan = useCallback(async (targetPlan: PaidPlanKey) => {
    const configured = catalog?.products.find(product => product.plan === targetPlan)
    const storeProduct = configured
      ? subscriptions.find(product => product.id === configured.product_id && product.platform === 'android')
      : null
    const offer = storeProduct?.platform === 'android'
      ? selectPlayOffer(storeProduct.subscriptionOffers, configured?.base_plan_id ?? null)
      : null
    if (!enabledForBuild || !catalog?.enabled || !billingStateVerified || !connected || !configured || !storeProduct || !offer?.offerTokenAndroid) {
      setError('Este plano não está disponível no Google Play para esta instalação.')
      return
    }
    if (!catalog.obfuscated_account_id) {
      setError('A conta ainda não está preparada para compras seguras no Google Play.')
      return
    }
    setProcessingProductId(configured.product_id)
    setOperation('purchase')
    setError('')
    setNotice('Confirmando a situação atual da assinatura…')
    try {
      const freshStatus = await getGooglePlayBillingStatus()
      if (!mountedRef.current) return
      setActiveProductId(freshStatus.active_product_id)
      setBillingStatus(freshStatus.billing_status)
      setBillingStateVerified(true)

      const preflightBillingState = playPurchasePreflightBillingState(freshStatus)
      if (blocksPlayPurchaseForExternalBilling(preflightBillingState)) {
        setProcessingProductId(null)
        setOperation(null)
        setError('Já existe uma assinatura externa ativa ou recuperável nesta conta. Conclua, restaure ou gerencie essa assinatura antes de comprar também pelo Google Play.')
        return
      }

      const freshActiveProductId = freshStatus.active_product_id
      if (configured.product_id === freshActiveProductId) {
        setProcessingProductId(null)
        setOperation(null)
        setNotice('Este já é o plano ativo desta conta.')
        return
      }

      setNotice('Abrindo a confirmação segura do Google Play…')
      const googleRequest: {
        skus: string[]
        subscriptionOffers: { sku: string; offerToken: string }[]
        obfuscatedAccountId: string
        purchaseToken?: string
        subscriptionProductReplacementParams?: {
          oldProductId: string
          replacementMode: 'charge-prorated-price' | 'deferred'
        }
      } = {
        skus: [configured.product_id],
        subscriptionOffers: [{ sku: configured.product_id, offerToken: offer.offerTokenAndroid }],
        obfuscatedAccountId: catalog.obfuscated_account_id,
      }

      if (freshActiveProductId) {
        const currentCatalogProduct = catalog.products.find(product => product.product_id === freshActiveProductId)
        const replacementMode = currentCatalogProduct
          ? replacementModeForPlans(currentCatalogProduct.plan, targetPlan)
          : null
        const available = await getAvailablePurchases({ includeSuspendedAndroid: true })
        const currentPurchase = available.find(purchase => (
          purchase.productId === freshActiveProductId && purchase.purchaseToken?.trim()
        ))
        if (!currentCatalogProduct || !replacementMode || !currentPurchase?.purchaseToken) {
          setError('Não foi possível localizar a assinatura atual no Google Play. Restaure a compra antes de mudar de plano.')
          setProcessingProductId(null)
          setOperation(null)
          return
        }
        googleRequest.purchaseToken = currentPurchase.purchaseToken
        googleRequest.subscriptionProductReplacementParams = {
          oldProductId: freshActiveProductId,
          replacementMode,
        }
      }

      await requestPurchase({ request: { google: googleRequest }, type: 'subs' })
    } catch (reason) {
      if (mountedRef.current) {
        setProcessingProductId(null)
        setOperation(null)
        setError(errorMessage(reason, 'Não foi possível iniciar a compra pelo Google Play.'))
      }
    }
  }, [billingStateVerified, catalog, connected, enabledForBuild, requestPurchase, subscriptions])

  const restore = useCallback(async () => {
    setError('')
    setNotice('Consultando compras desta conta do Google Play…')
    await queryAndReconcile('restore', true)
  }, [queryAndReconcile])

  const manageSubscription = useCallback(async () => {
    if (!catalog?.package_name) {
      setError('A página de gerenciamento do Google Play ainda não está disponível.')
      return
    }
    try {
      await deepLinkToSubscriptions({
        packageNameAndroid: catalog.package_name,
        skuAndroid: activeProductId,
      })
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível abrir o gerenciamento de assinaturas do Google Play.'))
    }
  }, [activeProductId, catalog])

  const retry = useCallback(async () => {
    setError('')
    setNotice('')
    await reconnect().catch(() => false)
    await loadBackendState()
  }, [loadBackendState, reconnect])

  const value: PlayBillingContextValue = {
    available: Boolean(enabledForBuild && catalog?.enabled && billingStateVerified),
    connected,
    loading,
    operation,
    processingProductId,
    activeProductId,
    billingStatus,
    error,
    notice,
    plans: planViews,
    purchasePlan,
    restorePurchases: restore,
    manageSubscription,
    retry,
  }

  return <PlayBillingContext.Provider value={value}>{children}</PlayBillingContext.Provider>
}
