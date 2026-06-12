import type { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Vera.Fidei - Biblioteca Catolica Digital',
    short_name: 'Vera.Fidei',
    description:
      'Biblioteca catolica digital com fontes primarias, oracoes, santos e verificacao de citacoes.',
    start_url: '/apresentacao',
    id: '/apresentacao',
    scope: '/',
    display: 'standalone',
    display_override: ['standalone', 'minimal-ui'],
    orientation: 'portrait',
    background_color: '#111111',
    theme_color: '#111111',
    categories: ['education', 'books', 'reference'],
    lang: 'pt-BR',
    icons: [
      {
        src: '/icons/icon-192.png',
        sizes: '192x192',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/icons/icon-512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/icons/icon-1024.png',
        sizes: '1024x1024',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/icons/maskable-512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'maskable',
      },
    ],
  }
}
