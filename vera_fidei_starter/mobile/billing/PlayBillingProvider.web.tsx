import type { PropsWithChildren } from 'react'

import { PLAY_PLAN_DETAILS, PAID_PLAN_KEYS } from '../lib/play-billing'
import { PlayBillingContext, type PlayBillingContextValue } from './PlayBillingContext'

const unavailable: PlayBillingContextValue = {
  available: false,
  connected: false,
  loading: false,
  operation: null,
  processingProductId: null,
  activeProductId: null,
  billingStatus: null,
  error: 'A cobrança pelo Google Play está disponível somente no aplicativo Android da loja.',
  notice: '',
  plans: PAID_PLAN_KEYS.map(plan => ({
    plan,
    ...PLAY_PLAN_DETAILS[plan],
    productId: null,
    displayPrice: 'Indisponível',
    offerTerms: '',
    available: false,
    current: false,
  })),
  purchasePlan: async () => undefined,
  restorePurchases: async () => undefined,
  manageSubscription: async () => undefined,
  retry: async () => undefined,
}

export default function PlayBillingProvider({ children }: PropsWithChildren) {
  return <PlayBillingContext.Provider value={unavailable}>{children}</PlayBillingContext.Provider>
}
