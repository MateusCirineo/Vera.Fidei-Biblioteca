import Image, { type StaticImageData } from 'next/image'

import diversas from '@/assets/oracoes/categories/diversas.webp'
import doutoresDaIgreja from '@/assets/oracoes/categories/doutores-da-igreja.webp'
import espiritoSanto from '@/assets/oracoes/categories/espirito-santo.webp'
import eucaristicas from '@/assets/oracoes/categories/eucaristicas.webp'
import marianas from '@/assets/oracoes/categories/marianas.webp'
import novenas from '@/assets/oracoes/categories/novenas.webp'
import oracoesAosSantos from '@/assets/oracoes/categories/oracoes-aos-santos.webp'
import oracoesAsSantas from '@/assets/oracoes/categories/oracoes-as-santas.webp'
import oracoesDiarias from '@/assets/oracoes/categories/oracoes-diarias.webp'
import paraLerABiblia from '@/assets/oracoes/categories/para-ler-a-biblia.webp'
import principaisOracoesDiarias from '@/assets/oracoes/categories/principais-oracoes-diarias.webp'
import saoJose from '@/assets/oracoes/categories/sao-jose.webp'
import sequenciasLiturgicas from '@/assets/oracoes/categories/sequencias-liturgicas.webp'
import viaSacra from '@/assets/oracoes/categories/via-sacra.webp'

interface PrayerCategoryIconProps {
  code: string
  className?: string
}

const CATEGORY_ARTWORK: Record<string, StaticImageData> = {
  MARIA: marianas,
  DIV: diversas,
  JOSE: saoJose,
  EUCA: eucaristicas,
  ESP: espiritoSanto,
  NOV: novenas,
  VIACR: viaSacra,
  SEQ: sequenciasLiturgicas,
  DOUT: doutoresDaIgreja,
  DIARIA: oracoesDiarias,
  BIBLIA: paraLerABiblia,
  BASE: principaisOracoesDiarias,
  SANTOS: oracoesAosSantos,
  SANTAS: oracoesAsSantas,
}

/** Artwork supplied for each prayer category; the surrounding title is its accessible name. */
export default function PrayerCategoryIcon({
  code,
  className = '',
}: PrayerCategoryIconProps) {
  const artwork = CATEGORY_ARTWORK[code] ?? principaisOracoesDiarias

  return (
    <Image
      src={artwork}
      alt=""
      aria-hidden="true"
      draggable={false}
      unoptimized
      className={`vf-prayer-category-image ${className}`.trim()}
    />
  )
}
