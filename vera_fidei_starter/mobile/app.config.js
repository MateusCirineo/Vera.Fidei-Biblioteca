const IS_DEV = process.env.APP_VARIANT === 'development'
const RAW_DISTRIBUTION_MODE = process.env.EXPO_PUBLIC_DISTRIBUTION_MODE
const DISTRIBUTION_MODE = RAW_DISTRIBUTION_MODE === 'direct' || RAW_DISTRIBUTION_MODE === 'play'
  ? RAW_DISTRIBUTION_MODE
  : 'reader'

export default ({ config }) => ({
  ...config,
  name: IS_DEV ? 'Vera.Fidei (Dev)' : 'Vera.Fidei',
  slug: 'vera-fidei',
  version: '1.2.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'dark',
  plugins: [
    'expo-font',
    'expo-iap',
    'expo-secure-store',
    'expo-sharing',
    [
      'expo-splash-screen',
      {
        image: './assets/splash-icon.png',
        imageWidth: 200,
        resizeMode: 'contain',
        backgroundColor: '#0b0b0e',
      },
    ],
  ],
  ios: {
    supportsTablet: false,
    bundleIdentifier: IS_DEV ? 'com.verafidei.app.dev' : 'com.verafidei.app',
    config: {
      usesNonExemptEncryption: false,
    },
  },
  android: {
    package: IS_DEV ? 'com.verafidei.app.dev' : 'com.verafidei.app',
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#0b0b0e',
    },
    predictiveBackGestureEnabled: false,
    permissions: [],
    blockedPermissions: [
      'android.permission.READ_EXTERNAL_STORAGE',
      'android.permission.WRITE_EXTERNAL_STORAGE',
      'android.permission.SYSTEM_ALERT_WINDOW',
    ],
  },
  web: {
    favicon: './assets/favicon.png',
  },
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://verafidei.com.br/api',
    webUrl: process.env.EXPO_PUBLIC_WEB_URL ?? 'https://verafidei.com.br',
    distributionMode: DISTRIBUTION_MODE,
    eas: {
      projectId: '88255b06-a482-42f8-bc2c-ea69ae091e04',
    },
  },
  updates: {
    fallbackToCacheTimeout: 0,
  },
  scheme: 'verafidei',
})
