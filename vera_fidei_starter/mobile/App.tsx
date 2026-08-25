import { NavigationContainer, DarkTheme } from '@react-navigation/native'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { Ionicons } from '@expo/vector-icons'
import { StatusBar } from 'expo-status-bar'
import { ActivityIndicator, Image, Platform, StyleSheet, Text, View } from 'react-native'
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context'

import { AuthProvider, useAuth } from './auth/AuthContext'
import PlayBillingProvider from './billing/PlayBillingProvider'
import { allowsAccountWeb, allowsPlayBilling } from './lib/distribution-policy'
import { DISTRIBUTION_MODE } from './lib/runtime-config'
import { colors } from './lib/theme'
import ApresentacaoScreen from './screens/ApresentacaoScreen'
import BibliotecaScreen from './screens/BibliotecaScreen'
import BookDetailScreen from './screens/BookDetailScreen'
import ForgotPasswordScreen from './screens/ForgotPasswordScreen'
import LoginScreen from './screens/LoginScreen'
import MoreScreen from './screens/MoreScreen'
import OracoesScreen from './screens/OracoesScreen'
import PdfWebViewScreen from './screens/PdfWebViewScreen'
import PlayPlansScreen from './screens/PlayPlansScreen'
import ProfileScreen from './screens/ProfileScreen'
import RegisterScreen from './screens/RegisterScreen'
import SantosScreen from './screens/SantosScreen'
import SearchScreen from './screens/SearchScreen'
import VerificadorScreen from './screens/VerificadorScreen'

const Tab = createBottomTabNavigator()
const AuthStack = createNativeStackNavigator()
const BibliotecaStack = createNativeStackNavigator()
const MoreStack = createNativeStackNavigator()
const RootStack = createNativeStackNavigator()

const navigationTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: colors.gold,
    background: colors.background,
    card: colors.card,
    border: colors.border,
    text: colors.text,
  },
}

function Header({ title }: { title: string }) {
  const insets = useSafeAreaInsets()
  return (
    <View style={[styles.header, { paddingTop: Math.max(insets.top, 10) }]}>
      <View style={styles.brandRow}>
        <Image source={require('./assets/logo.png')} style={styles.logo} resizeMode="contain" />
        <View style={styles.brandText}>
          <Text style={styles.brand}>Vera.Fidei</Text>
          <Text style={styles.subtitle}>Biblioteca Católica Digital</Text>
        </View>
        <Text style={styles.headerTitle}>{title}</Text>
      </View>
    </View>
  )
}

function BibliotecaNav() {
  return (
    <BibliotecaStack.Navigator screenOptions={{ headerShown: false }}>
      <BibliotecaStack.Screen name="BibliotecaMain" component={BibliotecaScreen} />
      <BibliotecaStack.Screen name="BookDetail" component={BookDetailScreen} />
    </BibliotecaStack.Navigator>
  )
}

const stackOptions = {
  headerStyle: { backgroundColor: colors.card },
  headerTintColor: colors.gold,
  headerTitleStyle: { color: colors.text, fontWeight: '800' as const },
  contentStyle: { backgroundColor: colors.background },
}

function MoreNav() {
  return (
    <MoreStack.Navigator screenOptions={stackOptions}>
      <MoreStack.Screen name="MaisInício" component={MoreScreen} options={{ title: 'Mais' }} />
      <MoreStack.Screen name="Santos" component={SantosScreen} />
      <MoreStack.Screen name="Orações" component={OracoesScreen} />
      <MoreStack.Screen name="Perfil" component={ProfileScreen} options={{ title: 'Meu perfil' }} />
    </MoreStack.Navigator>
  )
}

const tabs: {
  name: string
  title: string
  icon: keyof typeof Ionicons.glyphMap
  component: React.ComponentType<any>
  ownHeader?: boolean
}[] = [
  { name: 'Início', title: 'Vera.Fidei', icon: 'home-outline', component: ApresentacaoScreen },
  { name: 'Biblioteca', title: 'Biblioteca', icon: 'library-outline', component: BibliotecaNav },
  { name: 'Pesquisa', title: 'Pesquisa', icon: 'search-outline', component: SearchScreen },
  { name: 'Verificador', title: 'Verificador', icon: 'shield-checkmark-outline', component: VerificadorScreen },
  { name: 'Mais', title: 'Mais', icon: 'menu-outline', component: MoreNav, ownHeader: true },
]

function MainNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const tab = tabs.find(item => item.name === route.name)
          return <Ionicons name={tab?.icon ?? 'ellipse-outline'} size={size} color={color} />
        },
        tabBarActiveTintColor: colors.gold,
        tabBarInactiveTintColor: colors.tertiary,
        tabBarStyle: styles.tabBar,
        tabBarLabelStyle: styles.tabLabel,
        headerTitle: () => null,
      })}
    >
      {tabs.map(tab => (
        <Tab.Screen
          key={tab.name}
          name={tab.name}
          component={tab.component}
          options={{
            headerShown: !tab.ownHeader,
            header: tab.ownHeader ? undefined : () => <Header title={tab.title} />,
          }}
        />
      ))}
    </Tab.Navigator>
  )
}

function AuthenticatedNavigator() {
  return (
    <RootStack.Navigator screenOptions={stackOptions}>
      <RootStack.Screen name="AbasPrincipais" component={MainNavigator} options={{ headerShown: false }} />
      <RootStack.Screen
        name="LeitorPdf"
        component={PdfWebViewScreen}
        options={{ title: 'Conferir no PDF', presentation: 'fullScreenModal' }}
      />
      {allowsAccountWeb(DISTRIBUTION_MODE, 'profile') ? (
        <RootStack.Screen
          name="ContaWeb"
          component={PdfWebViewScreen}
          options={{ title: 'Conta e assinatura', presentation: 'fullScreenModal' }}
        />
      ) : null}
      {allowsPlayBilling(DISTRIBUTION_MODE, Platform.OS) ? (
        <RootStack.Screen
          name="PlayPlans"
          component={PlayPlansScreen}
          options={{ title: 'Planos Google Play', presentation: 'modal' }}
        />
      ) : null}
    </RootStack.Navigator>
  )
}

function AuthenticatedApp() {
  const navigator = <AuthenticatedNavigator />
  return allowsPlayBilling(DISTRIBUTION_MODE, Platform.OS)
    ? <PlayBillingProvider>{navigator}</PlayBillingProvider>
    : navigator
}

function AuthNavigator() {
  return (
    <AuthStack.Navigator screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="Entrar" component={LoginScreen} />
      <AuthStack.Screen name="CriarConta" component={RegisterScreen} />
      <AuthStack.Screen name="RecuperarSenha" component={ForgotPasswordScreen} />
    </AuthStack.Navigator>
  )
}

function AppGate() {
  const { status } = useAuth()
  if (status === 'loading') {
    return (
      <View style={styles.loading}>
        <Image source={require('./assets/logo.png')} style={styles.loadingLogo} resizeMode="contain" />
        <ActivityIndicator color={colors.gold} size="large" />
        <Text style={styles.loadingText}>Abrindo o Vera.Fidei…</Text>
      </View>
    )
  }
  return (
    <NavigationContainer theme={navigationTheme}>
      {status === 'authenticated' ? <AuthenticatedApp /> : <AuthNavigator />}
    </NavigationContainer>
  )
}

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <AuthProvider><AppGate /></AuthProvider>
    </SafeAreaProvider>
  )
}

const styles = StyleSheet.create({
  header: { backgroundColor: colors.background, paddingBottom: 11, paddingHorizontal: 14, borderBottomWidth: 1, borderBottomColor: colors.border },
  brandRow: { minHeight: 42, flexDirection: 'row', alignItems: 'center', gap: 9 },
  logo: { width: 34, height: 34 },
  brandText: { flexShrink: 1 },
  brand: { fontSize: 15, fontWeight: '900', color: colors.text },
  subtitle: { fontSize: 10, color: colors.gold, fontWeight: '700' },
  headerTitle: { marginLeft: 'auto', color: colors.muted, fontSize: 14, fontWeight: '800' },
  tabBar: { backgroundColor: colors.card, borderTopColor: colors.border, height: 68, paddingBottom: 9, paddingTop: 7 },
  tabLabel: { fontSize: 10, fontWeight: '800' },
  loading: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center', gap: 13 },
  loadingLogo: { width: 92, height: 92 },
  loadingText: { color: colors.muted },
})
