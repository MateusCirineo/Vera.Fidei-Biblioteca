import { createContext, useContext } from 'react'

import type { PaidPlanKey, PlayPlanDetails } from '../lib/play-billing'

export type PlayPlanView = PlayPlanDetails & {
  plan: PaidPlanKey
  productId: string | null
  displayPrice: string
  offerTerms: string
  available: boolean
  current: boolean
}

export type PlayBillingContextValue = {
  available: boolean
  connected: boolean
  loading: boolean
  operation: 'purchase' | 'restore' | 'sync' | null
  processingProductId: string | null
  activeProductId: string | null
  billingStatus: string | null
  error: string
  notice: string
  plans: PlayPlanView[]
  purchasePlan: (plan: PaidPlanKey) => Promise<void>
  restorePurchases: () => Promise<void>
  manageSubscription: () => Promise<void>
  retry: () => Promise<void>
}

export const PlayBillingContext = createContext<PlayBillingContextValue | null>(null)

export function usePlayBilling(): PlayBillingContextValue {
  const value = useContext(PlayBillingContext)
  if (!value) throw new Error('A cobrança Google Play não está disponível neste modo do aplicativo.')
  return value
}
