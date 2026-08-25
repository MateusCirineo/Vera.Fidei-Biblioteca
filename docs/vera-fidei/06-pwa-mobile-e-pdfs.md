# PWA, Mobile E PDFs

## PWA

O Vera.Fidei funciona como PWA, ou seja, pode ser instalado no celular como aplicativo a partir do navegador.

No iPhone, o uso como PWA depende do Safari e da opção de adicionar à tela de início.

## Fluxos Importantes No Mobile

O app mobile/PWA precisa funcionar bem em:

- cadastro;
- login;
- biblioteca;
- abertura de PDF;
- busca no PDF;
- zoom do PDF;
- orações;
- planos;
- perfil.

## Visualizador De PDF

O visualizador de PDF do Vera.Fidei foi pensado para funcionar dentro do app, especialmente no mobile.

Ele deve permitir:

- voltar;
- ver a página atual;
- ir para uma página específica;
- aumentar zoom;
- diminuir zoom;
- buscar palavra ou trecho;
- rolar o PDF;
- manter a interface dentro da área segura da tela.

## Diferença Entre Zoom Do PDF E Zoom Do App

O zoom deve afetar o PDF, não a página inteira do app.

Isso evita bugs visuais no PWA e impede que botões, abas ou barras fiquem fora da tela.

## Busca No PDF

A busca textual dentro do PDF depende de o PDF possuir texto extraível.

Quando o PDF é apenas imagem escaneada, pode ser necessário OCR antes para que a busca funcione corretamente.

## iPhone E Área Segura

Em iPhones com notch, barra superior ou modo PWA instalado, o app precisa respeitar:

- `safe-area-inset-top`;
- `safe-area-inset-bottom`;
- altura real da viewport;
- orientação vertical;
- largura disponível do dispositivo.

## Performance

Para o app parecer profissional no celular, os fluxos devem abrir rapidamente:

- orações;
- biblioteca;
- PDF;
- perfil;
- planos.

PDFs grandes podem demorar mais, mas a interface deve aparecer rápido e informar carregamento.
