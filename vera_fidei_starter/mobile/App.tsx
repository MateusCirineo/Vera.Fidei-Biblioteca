import { NavigationContainer } from '@react-navigation/native'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { Ionicons } from '@expo/vector-icons'
import { StatusBar } from 'expo-status-bar'
import { Image, StyleSheet, Text, View } from 'react-native'

import ApresentacaoScreen from './screens/ApresentacaoScreen'
import BibliotecaScreen from './screens/BibliotecaScreen'
import BookDetailScreen from './screens/BookDetailScreen'
import VerificadorScreen from './screens/VerificadorScreen'
import SantosScreen from './screens/SantosScreen'
import OracoesScreen from './screens/OracoesScreen'

const Tab = createBottomTabNavigator()
const BibliotecaStack = createNativeStackNavigator()

const GOLD = '#c9a84c'
const BG = '#111111'
const CARD = '#1a1a1a'
const BORDER = '#2a2a2a'
const TEXT = '#f5f0e8'
const MUTED = '#b8b0a0'

function Header({ title }: { title: string }) {
  return (
    <View style={styles.header}>
      <View style={styles.brandRow}>
        <Image source={require('./assets/logo.png')} style={styles.logo} resizeMode="contain" />
        <View>
          <Text style={styles.brand}>Vera.Fidei</Text>
          <Text style={styles.subtitle}>Biblioteca Católica Digital</Text>
        </View>
      </View>
      <Text style={styles.headerTitle}>{title}</Text>
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

const TABS: {
  name: string
  title: string
  icon: keyof typeof Ionicons.glyphMap
  component: React.ComponentType<any>
}[] = [
  { name: 'Apresentação', title: 'Vera.Fidei', icon: 'book-outline', component: ApresentacaoScreen },
  { name: 'Biblioteca', title: 'Biblioteca', icon: 'library-outline', component: BibliotecaNav },
  { name: 'Verificador', title: 'Verificador', icon: 'search-outline', component: VerificadorScreen },
  { name: 'Santos', title: 'Santos', icon: 'star-outline', component: SantosScreen },
  { name: 'Orações', title: 'Orações', icon: 'rose-outline', component: OracoesScreen },
]

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ color, size }) => {
            const tab = TABS.find(t => t.name === route.name)
            return <Ionicons name={tab?.icon ?? 'ellipse-outline'} size={size} color={color} />
          },
          tabBarActiveTintColor: GOLD,
          tabBarInactiveTintColor: '#706860',
          tabBarStyle: styles.tabBar,
          tabBarLabelStyle: styles.tabLabel,
          headerShown: true,
          headerTitle: () => null,
        })}
      >
        {TABS.map(({ name, title, component }) => (
          <Tab.Screen
            key={name}
            name={name}
            component={component}
            options={{ header: () => <Header title={title} /> }}
          />
        ))}
      </Tab.Navigator>
    </NavigationContainer>
  )
}

const styles = StyleSheet.create({
  header: {
    backgroundColor: BG,
    paddingTop: 52,
    paddingBottom: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logo: { width: 34, height: 34 },
  brand: { fontSize: 16, fontWeight: '800', color: TEXT },
  subtitle: { fontSize: 11, color: GOLD, fontWeight: '700' },
  headerTitle: { fontSize: 24, fontWeight: '800', color: TEXT, marginTop: 10 },
  tabBar: {
    backgroundColor: CARD,
    borderTopColor: BORDER,
    height: 68,
    paddingBottom: 9,
    paddingTop: 8,
  },
  tabLabel: { fontSize: 10, fontWeight: '700' },
})
