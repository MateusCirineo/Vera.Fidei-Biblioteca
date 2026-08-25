const PLAN_LEVEL: Record<string, number> = {
  fiel: 0,
  catequista: 1,
  apologeta: 2,
  patristico: 3,
  magisterio: 4,
}

export function normalizedPlan(plan: string | null | undefined): string {
  const value = plan?.trim().toLowerCase() ?? 'fiel'
  return value in PLAN_LEVEL ? value : 'fiel'
}

export function canOpenLibraryPdf(plan: string | null | undefined): boolean {
  return PLAN_LEVEL[normalizedPlan(plan)] >= PLAN_LEVEL.apologeta
}

export function planLabel(plan: string | null | undefined): string {
  const labels: Record<string, string> = {
    fiel: 'Fiel',
    catequista: 'Catequista',
    apologeta: 'Apologeta',
    patristico: 'Patrístico',
    magisterio: 'Magistério',
  }
  return labels[normalizedPlan(plan)]
}
