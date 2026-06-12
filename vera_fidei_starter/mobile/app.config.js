const IS_DEV = process.env.APP_VARIANT === 'development'

export default ({ config }) => ({
  ...config,
  name: IS_DEV ? 'Vera.Fidei (Dev)' : 'Vera.Fidei',
  slug: 'vera-fidei',
  version: '1.2.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'light',
  newArchEnabled: true,
  splash: {
    image: './assets/splash-icon.png',
    resizeMode: 'contain',
    backgroundColor: '#1a1a2e',
  },
  ios: {
    supportsTablet: true,
    bundleIdentifier: IS_DEV ? 'com.verafidei.app.dev' : 'com.verafidei.app',
    buildNumber: '1',
    infoPlist: {
      NSAppTransportSecurity: {
        // Permite HTTP durante desenvolvimento/servidor sem HTTPS
        // Remover após configurar HTTPS no servidor
        NSAllowsArbitraryLoads: true,
      },
    },
  },
  android: {
    package: IS_DEV ? 'com.verafidei.app.dev' : 'com.verafidei.app',
    versionCode: 1,
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#1e3a5f',
    },
    edgeToEdgeEnabled: true,
    predictiveBackGestureEnabled: false,
    permissions: [],
  },
  web: {
    favicon: './assets/favicon.png',
  },
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://verafidei.oialfred.com/api',
    apiKey: process.env.EXPO_PUBLIC_API_KEY ?? '',
    eas: {
      projectId: '88255b06-a482-42f8-bc2c-ea69ae091e04',
    },
  },
  updates: {
    fallbackToCacheTimeout: 0,
  },
})
