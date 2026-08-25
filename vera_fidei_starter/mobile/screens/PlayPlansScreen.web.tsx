import { StyleSheet, Text, TouchableOpacity, View } from 'react-native'

import { colors } from '../lib/theme'

export default function PlayPlansScreen({ navigation }: { navigation: any }) {
  return (
    <View style={styles.root}>
      <Text style={styles.title}>Planos do Google Play</Text>
      <Text style={styles.text}>
        A assinatura pelo Google Play está disponível somente no aplicativo Android instalado pela loja.
      </Text>
      <TouchableOpacity style={styles.button} onPress={() => navigation.goBack()}>
        <Text style={styles.buttonText}>Voltar</Text>
      </TouchableOpacity>
    </View>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24 },
  title: { color: colors.text, fontSize: 21, fontWeight: '900', textAlign: 'center' },
  text: { color: colors.muted, textAlign: 'center', lineHeight: 20 },
  button: { borderWidth: 1, borderColor: '#6b5721', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 10 },
  buttonText: { color: colors.gold, fontWeight: '900' },
})
