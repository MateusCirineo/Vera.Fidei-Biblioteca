import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'

import { useAuth } from '../auth/AuthContext'
import { usePlayBilling } from '../billing/PlayBillingContext'
import type { PaidPlanKey } from '../lib/play-billing'
import { colors } from '../lib/theme'

function PlanCard({ plan }: { plan: ReturnType<typeof usePlayBilling>['plans'][number] }) {
  const { user } = useAuth()
  const {
    loading,
    operation,
    processingProductId,
    purchasePlan,
  } = usePlayBilling()
  const isCurrent = plan.current || user?.plan?.toLowerCase() === plan.plan
  const isProcessing = operation === 'purchase' && processingProductId === plan.productId
  const disabled = loading || operation !== null || !plan.available || isCurrent

  return (
    <View style={[styles.planCard, isCurrent && styles.currentCard]}>
      <View style={styles.planHeader}>
        <View style={styles.planHeading}>
          <Text style={styles.audience}>{plan.audience}</Text>
          <Text style={styles.planName}>{plan.label}</Text>
        </View>
        {isCurrent ? <Text style={styles.currentBadge}>Plano atual</Text> : null}
      </View>
      <Text style={styles.price}>{plan.displayPrice}</Text>
      {plan.offerTerms ? <Text style={styles.offerTerms}>{plan.offerTerms}</Text> : null}
      <Text style={styles.limit}>{plan.verificationLimit}</Text>
      <View style={styles.featureList}>
        {plan.features.map(feature => <Text key={feature} style={styles.feature}>✓ {feature}</Text>)}
      </View>
      <TouchableOpacity
        accessibilityRole="button"
        disabled={disabled}
        onPress={() => void purchasePlan(plan.plan as PaidPlanKey)}
        style={[styles.primaryButton, disabled && styles.disabledButton]}
      >
        {isProcessing ? <ActivityIndicator color="#16120b" /> : null}
        <Text style={styles.primaryButtonText}>
          {isCurrent
            ? 'Plano atual'
            : isProcessing
              ? 'Aguardando Google Play…'
              : plan.available
                ? 'Escolher pelo Google Play'
                : 'Indisponível'}
        </Text>
      </TouchableOpacity>
    </View>
  )
}

export default function PlayPlansScreen({ navigation }: { navigation: any }) {
  const {
    activeProductId,
    available,
    billingStatus,
    connected,
    error,
    loading,
    manageSubscription,
    notice,
    operation,
    plans,
    restorePurchases,
    retry,
  } = usePlayBilling()

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <TouchableOpacity onPress={() => navigation.goBack()}>
        <Text style={styles.back}>‹ Voltar</Text>
      </TouchableOpacity>
      <View style={styles.intro}>
        <Text style={styles.eyebrow}>ASSINATURA ANDROID</Text>
        <Text style={styles.title}>Planos pelo Google Play</Text>
        <Text style={styles.description}>
          O preço, a moeda e eventuais ofertas abaixo vêm diretamente do Google Play para sua conta e seu país.
        </Text>
      </View>

      {loading ? (
        <View style={styles.statusRow}>
          <ActivityIndicator color={colors.gold} />
          <Text style={styles.statusText}>Consultando planos e assinatura…</Text>
        </View>
      ) : null}
      {notice ? <Text style={styles.notice}>{notice}</Text> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {!available || !connected ? (
        <TouchableOpacity
          disabled={loading || operation !== null}
          onPress={() => void retry()}
          style={[styles.secondaryButton, (loading || operation !== null) && styles.disabledButton]}
        >
          <Text style={styles.secondaryButtonText}>Tentar novamente</Text>
        </TouchableOpacity>
      ) : null}

      {plans.map(plan => <PlanCard key={plan.plan} plan={plan} />)}

      <View style={styles.actionsCard}>
        <Text style={styles.actionsTitle}>Sua assinatura</Text>
        {billingStatus ? <Text style={styles.statusText}>Situação: {billingStatus}</Text> : null}
        <TouchableOpacity
          disabled={loading || operation !== null}
          onPress={() => void restorePurchases()}
          style={[styles.secondaryButton, (loading || operation !== null) && styles.disabledButton]}
        >
          {operation === 'restore' ? <ActivityIndicator color={colors.gold} /> : null}
          <Text style={styles.secondaryButtonText}>Restaurar compras</Text>
        </TouchableOpacity>
        {activeProductId ? (
          <TouchableOpacity
            disabled={operation !== null}
            onPress={() => void manageSubscription()}
            style={[styles.secondaryButton, operation !== null && styles.disabledButton]}
          >
            <Text style={styles.secondaryButtonText}>Gerenciar no Google Play</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      <View style={styles.disclosure}>
        <Text style={styles.disclosureTitle}>Informações da assinatura</Text>
        <Text style={styles.disclosureText}>
          A assinatura é renovada automaticamente no período exibido pelo Google Play, salvo cancelamento antes da renovação. O pagamento é cobrado pela sua conta Google Play. Você pode cancelar ou gerenciar a assinatura nas configurações do Google Play. O acesso pago só é liberado depois da confirmação do Google Play e do Vera Fidei. Sua conta gratuita continua disponível se a assinatura terminar.
        </Text>
      </View>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { padding: 16, paddingBottom: 48, gap: 12 },
  back: { color: colors.gold, fontWeight: '800', paddingVertical: 4 },
  intro: { gap: 5, marginBottom: 3 },
  eyebrow: { color: colors.gold, fontSize: 11, fontWeight: '900', letterSpacing: 1.1 },
  title: { color: colors.text, fontSize: 25, fontWeight: '900' },
  description: { color: colors.muted, lineHeight: 20 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 9, padding: 12, borderRadius: 8, backgroundColor: colors.card },
  statusText: { color: colors.muted, lineHeight: 18 },
  notice: { color: '#d1fae5', backgroundColor: '#064e3b66', borderColor: '#047857', borderWidth: 1, borderRadius: 8, padding: 11, lineHeight: 18 },
  error: { color: '#fecaca', backgroundColor: '#7f1d1d44', borderColor: '#991b1b', borderWidth: 1, borderRadius: 8, padding: 11, lineHeight: 18 },
  planCard: { gap: 9, backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1, borderRadius: 12, padding: 15 },
  currentCard: { borderColor: colors.gold },
  planHeader: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 },
  planHeading: { flex: 1 },
  audience: { color: colors.tertiary, fontSize: 10, fontWeight: '900', textTransform: 'uppercase', letterSpacing: 0.7 },
  planName: { color: colors.text, fontSize: 20, fontWeight: '900', marginTop: 2 },
  currentBadge: { color: colors.gold, backgroundColor: colors.goldSoft, borderRadius: 12, overflow: 'hidden', paddingHorizontal: 8, paddingVertical: 4, fontSize: 10, fontWeight: '900' },
  price: { color: colors.gold, fontSize: 22, fontWeight: '900' },
  offerTerms: { color: colors.muted, fontSize: 12, lineHeight: 17 },
  limit: { color: colors.text, fontWeight: '700' },
  featureList: { gap: 4 },
  feature: { color: colors.muted, fontSize: 12, lineHeight: 18 },
  primaryButton: { minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: colors.gold, borderRadius: 8, paddingHorizontal: 12 },
  primaryButtonText: { color: '#16120b', fontWeight: '900', textAlign: 'center' },
  secondaryButton: { minHeight: 46, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: colors.card, borderColor: '#6b5721', borderWidth: 1, borderRadius: 8, paddingHorizontal: 12 },
  secondaryButtonText: { color: colors.gold, fontWeight: '900', textAlign: 'center' },
  disabledButton: { opacity: 0.5 },
  actionsCard: { gap: 9, backgroundColor: colors.cardRaised, borderColor: colors.border, borderWidth: 1, borderRadius: 12, padding: 14 },
  actionsTitle: { color: colors.text, fontSize: 17, fontWeight: '900' },
  disclosure: { gap: 6, padding: 13, borderRadius: 10, borderWidth: 1, borderColor: colors.border },
  disclosureTitle: { color: colors.text, fontWeight: '900' },
  disclosureText: { color: colors.tertiary, fontSize: 11, lineHeight: 17 },
})
