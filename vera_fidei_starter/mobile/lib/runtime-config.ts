import Constants from 'expo-constants'

import { normalizeBaseUrl } from './url'

const extra = Constants.expoConfig?.extra ?? {}

export const API_BASE = normalizeBaseUrl(
  typeof extra.apiUrl === 'string' ? extra.apiUrl : 'https://verafidei.oialfred.com/api',
)

export const WEB_BASE = normalizeBaseUrl(
  typeof extra.webUrl === 'string' ? extra.webUrl : 'https://verafidei.oialfred.com',
)
