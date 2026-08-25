import * as SecureStore from 'expo-secure-store'
import { Platform } from 'react-native'

const TOKEN_KEY = 'vera_fidei_access_token'

export async function readSecureToken(): Promise<string | null> {
  if (Platform.OS === 'web') return null
  return SecureStore.getItemAsync(TOKEN_KEY)
}

export async function saveSecureToken(token: string): Promise<void> {
  if (Platform.OS === 'web') return
  await SecureStore.setItemAsync(TOKEN_KEY, token, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  })
}

export async function deleteSecureToken(): Promise<void> {
  if (Platform.OS === 'web') return
  await SecureStore.deleteItemAsync(TOKEN_KEY)
}
