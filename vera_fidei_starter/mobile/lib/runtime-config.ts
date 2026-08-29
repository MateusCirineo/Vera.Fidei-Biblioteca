import Constants from 'expo-constants'

import { normalizeDistributionMode } from './distribution-policy'
import { normalizeBaseUrl } from './url'

const extra = Constants.expoConfig?.extra ?? {}

export const API_BASE = normalizeBaseUrl(
  typeof extra.apiUrl === 'string' ? extra.apiUrl : 'https://verafidei.com.br/api',
)

export const WEB_BASE = normalizeBaseUrl(
  typeof extra.webUrl === 'string' ? extra.webUrl : 'https://verafidei.com.br',
)

export const DISTRIBUTION_MODE = normalizeDistributionMode(extra.distributionMode)
