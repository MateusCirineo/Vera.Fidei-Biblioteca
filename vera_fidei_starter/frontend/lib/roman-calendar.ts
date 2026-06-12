export type SaintSource = {
  label: string
  url?: string
}

export type SaintHagiography = {
  storyTitle: string
  history: string[]
  witness: string[]
  devotion: string[]
  virtues: string[]
  prayer: string
  otherCelebrations: string[]
  sources: SaintSource[]
}

export type CalendarSaint = {
  key: string
  dateLabel: string
  name: string
  rank: string
  summary: string
  theme: string
  aliases: string[]
  hagiography: SaintHagiography
}

export type SaintWorkProfile = {
  name: string
  title: string
  century: string
  collection: string
  summary: string
  aliases: string[]
}

const MONTH_SAINTS: Record<number, string[]> = {
  1: [
    'Santa Maria, Mãe de Deus',
    'São Basílio Magno e São Gregório Nazianzeno',
    'Santíssimo Nome de Jesus',
    'Santa Ângela de Foligno',
    'São João Nepomuceno Neumann',
    'Santo André Bessette',
    'São Raimundo de Peñafort',
    'São Lourenço Justiniano',
    'Santo Adriano',
    'São Gregório de Nissa',
    'São Teodósio Cenobita',
    'Santo Antônio Maria Pucci',
    'Santo Hilário de Poitiers',
    'São Félix de Nola',
    'Santo Amaro',
    'São Marcelo I',
    'Santo Antão',
    'Santa Margarida da Hungria',
    'São Canuto',
    'São Fabiano e São Sebastião',
    'Santa Inês',
    'São Vicente',
    'Santo Ildefonso',
    'São Francisco de Sales',
    'Conversão de São Paulo',
    'São Timóteo e São Tito',
    'Santa Ângela Merici',
    'São Tomás de Aquino',
    'São Valério',
    'Santa Martina',
    'São João Bosco',
  ],
  2: [
    'Santa Brígida da Irlanda',
    'Apresentação do Senhor',
    'São Brás e Santo Ansgário',
    'Santa Joana de Valois',
    'Santa Águeda',
    'São Paulo Miki e companheiros',
    'Beato Pio IX',
    'Santa Josefina Bakhita',
    'Santa Apolônia',
    'Santa Escolástica',
    'Nossa Senhora de Lourdes',
    'Santa Eulália',
    'Santa Catarina de Ricci',
    'São Cirilo e São Metódio',
    'São Cláudio de La Colombière',
    'Santa Juliana',
    'Sete Santos Fundadores dos Servitas',
    'São Simeão',
    'São Conrado de Placência',
    'Santos Francisco e Jacinta Marto',
    'São Pedro Damião',
    'Cátedra de São Pedro',
    'São Policarpo',
    'São Sérgio',
    'São Cesário',
    'São Porfírio de Gaza',
    'São Gabriel da Virgem Dolorosa',
    'Santo Osvaldo',
    'Santo Augusto Chapdelaine',
  ],
  3: [
    'São David de Gales',
    'Santa Inês de Praga',
    'Santa Cunegundes',
    'São Casimiro',
    'São João José da Cruz',
    'Santa Rosa de Viterbo',
    'Santas Perpétua e Felicidade',
    'São João de Deus',
    'Santa Francisca Romana',
    'Santos Quarenta Mártires de Sebaste',
    'Santo Eulógio de Córdoba',
    'São Luís Orione',
    'São Nicéforo',
    'Santa Matilde',
    'Santa Luísa de Marillac',
    'São Heriberto',
    'São Patrício',
    'São Cirilo de Jerusalém',
    'São José',
    'São Martinho de Braga',
    'São Nicolau de Flüe',
    'Santa Léia',
    'São Toríbio de Mogrovejo',
    'Santa Catarina da Suécia',
    'Anunciação do Senhor',
    'São Ludgero',
    'São Ruperto',
    'São Gontrão',
    'São Bertoldo',
    'São João Clímaco',
    'São Benjamim',
  ],
  4: [
    'Santo Hugo de Grenoble',
    'São Francisco de Paula',
    'São Ricardo',
    'Santo Isidoro de Sevilha',
    'São Vicente Ferrer',
    'São Marcelino',
    'São João Batista de La Salle',
    'Santa Júlia Billiart',
    'Santa Maria de Cléofas',
    'Santa Madalena de Canossa',
    'Santo Estanislau',
    'São Júlio I',
    'São Martinho I',
    'São Tibúrcio',
    'Santa Anastásia',
    'Santa Bernadete Soubirous',
    'Santo Aniceto',
    'Santo Apolônio',
    'São Leão IX',
    'Santa Inês de Montepulciano',
    'Santo Anselmo',
    'São Sotero',
    'São Jorge',
    'São Fidélis de Sigmaringa',
    'São Marcos Evangelista',
    'Nossa Senhora do Bom Conselho',
    'Santa Zita',
    'São Pedro Chanel',
    'Santa Catarina de Sena',
    'São Pio V',
  ],
  5: [
    'São José Operário',
    'Santo Atanásio',
    'São Filipe e São Tiago',
    'São Ciríaco',
    'Santo Hilário de Arles',
    'São Domingos Sávio',
    'Santa Flávia Domitila',
    'Nossa Senhora do Rosário de Pompeia',
    'São Pacômio',
    'São João de Ávila',
    'Santo Inácio de Láconi',
    'São Nereu e Santo Aquiles',
    'Nossa Senhora de Fátima',
    'São Matias',
    'Santo Isidoro Lavrador',
    'São Simão Stock',
    'São Pascoal Bailão',
    'São João I',
    'São Celestino V',
    'São Bernardino de Sena',
    'São Cristóvão Magalhães e companheiros',
    'Santa Rita de Cássia',
    'São João Batista de Rossi',
    'Nossa Senhora Auxiliadora',
    'São Beda Venerável',
    'São Filipe Néri',
    'Santo Agostinho de Cantuária',
    'São Germano de Paris',
    'São Paulo VI',
    "Santa Joana d'Arc",
    'Visitação de Nossa Senhora',
  ],
  6: [
    'São Justino',
    'São Marcelino e São Pedro',
    'São Carlos Lwanga e companheiros',
    'São Francisco Caracciolo',
    'São Bonifácio',
    'São Norberto',
    'São Roberto de Newminster',
    'São Medardo',
    'Santo Efrém',
    'São Getúlio',
    'São Barnabé',
    'Santo Onofre',
    'Santo Antônio de Pádua',
    'Santo Eliseu',
    'Santa Germana Cousin',
    'São João Francisco Régis',
    'Santo Adolfo',
    'São Gregório Barbarigo',
    'São Romualdo',
    'São Silverio',
    'São Luís Gonzaga',
    'São Paulino de Nola, São João Fisher e São Tomás More',
    'São José Cafasso',
    'Natividade de São João Batista',
    'São Guilherme de Vercelli',
    'São Josemaria Escrivá',
    'São Cirilo de Alexandria',
    'Santo Irineu de Lião',
    'São Pedro e São Paulo',
    'Primeiros Mártires da Igreja de Roma',
  ],
  7: [
    'Santo Aarão',
    'São Bernardino Realino',
    'São Tomé Apóstolo',
    'Santa Isabel de Portugal',
    'Santo Antônio Maria Zaccaria',
    'Santa Maria Goretti',
    'Santo Otão',
    'Santo Adriano III',
    'Santos Agostinho Zhao Rong e companheiros',
    'Santa Verônica Giuliani',
    'São Bento',
    'São João Gualberto',
    'Santo Henrique',
    'São Camilo de Lellis',
    'São Boaventura',
    'Nossa Senhora do Carmo',
    'Santo Aleixo',
    'São Frederico',
    'Santo Arsênio',
    'Santo Apolinário',
    'São Lourenço de Bríndisi',
    'Santa Maria Madalena',
    'Santa Brígida da Suécia',
    'São Charbel Makhlouf',
    'São Tiago Apóstolo',
    'São Joaquim e Santa Ana',
    'São Pantaleão',
    'Santo Inocêncio I',
    'Santa Marta, Santa Maria e São Lázaro',
    'São Pedro Crisólogo',
    'Santo Inácio de Loyola',
  ],
  8: [
    'Santo Afonso Maria de Ligório',
    'Santo Eusébio de Vercelli',
    'Santa Lídia',
    'São João Maria Vianney',
    'Dedicação da Basílica de Santa Maria Maior',
    'Transfiguração do Senhor',
    'São Sisto II e companheiros',
    'São Domingos',
    'Santa Teresa Benedita da Cruz',
    'São Lourenço',
    'Santa Clara',
    'Santa Joana Francisca de Chantal',
    'Santa Dulce dos Pobres',
    'São Maximiliano Maria Kolbe',
    'Assunção de Nossa Senhora',
    'Santo Estêvão da Hungria',
    'Santa Beatriz da Silva',
    'Santa Helena',
    'São João Eudes',
    'São Bernardo de Claraval',
    'São Pio X',
    'Nossa Senhora Rainha',
    'Santa Rosa de Lima',
    'São Bartolomeu',
    'São Luís IX e São José de Calasanz',
    'Santa Teresa de Jesus Jornet',
    'Santa Mônica',
    'Santo Agostinho',
    'Martírio de São João Batista',
    'Santa Joana Jugan',
    'São Raimundo Nonato',
  ],
  9: [
    'Santo Egídio',
    'Santa Ingrid da Suécia',
    'São Gregório Magno',
    'Santa Rosa de Viterbo',
    'Santa Teresa de Calcutá',
    'São Magno',
    'São Clodoaldo',
    'Natividade de Nossa Senhora',
    'São Pedro Claver',
    'São Nicolau de Tolentino',
    'São João Gabriel Perboyre',
    'Santíssimo Nome de Maria',
    'São João Crisóstomo',
    'Exaltação da Santa Cruz',
    'Nossa Senhora das Dores',
    'São Cornélio e São Cipriano',
    'São Roberto Belarmino',
    'São José de Cupertino',
    'São Januário',
    'Santo André Kim Taegon e companheiros',
    'São Mateus',
    'São Maurício e companheiros',
    'São Pio de Pietrelcina',
    'São Sérgio de Radonej',
    'São Firmino',
    'São Cosme e São Damião',
    'São Vicente de Paulo',
    'São Venceslau',
    'Santos Miguel, Gabriel e Rafael',
    'São Jerônimo',
  ],
  10: [
    'Santa Teresinha do Menino Jesus',
    'Santos Anjos da Guarda',
    'São Dionísio Areopagita',
    'São Francisco de Assis',
    'Santa Faustina Kowalska',
    'São Bruno',
    'Nossa Senhora do Rosário',
    'Santa Reparata',
    'São Dionísio e companheiros, São João Leonardi',
    'São Daniel Comboni',
    'São João XXIII',
    'Nossa Senhora Aparecida',
    'Santo Eduardo',
    'São Calisto I',
    'Santa Teresa de Jesus',
    'Santa Margarida Maria Alacoque',
    'Santo Inácio de Antioquia',
    'São Lucas Evangelista',
    'São Paulo da Cruz, Santos João de Brébeuf e Isaac Jogues',
    'Santa Maria Bertilla Boscardin',
    'Santa Úrsula',
    'São João Paulo II',
    'São João de Capistrano',
    'Santo Antônio Maria Claret',
    "Santo Antônio de Sant'Ana Galvão",
    'Santo Evaristo',
    'São Frumêncio',
    'São Simão e São Judas',
    'Santo Honorato',
    'Santo Afonso Rodrigues',
    'São Quintino',
  ],
  11: [
    'Todos os Santos',
    'Fiéis Defuntos',
    'São Martinho de Porres',
    'São Carlos Borromeu',
    'São Zacarias e Santa Isabel',
    'São Nuno de Santa Maria',
    'São Vilibrordo',
    'Santo Godofredo',
    'Dedicação da Basílica de São João de Latrão',
    'São Leão Magno',
    'São Martinho de Tours',
    'São Josafá',
    'Santo Estanislau Kostka',
    'São Serapião',
    'Santo Alberto Magno',
    'Santa Gertrudes',
    'Santa Isabel da Hungria',
    'Dedicação das Basílicas de São Pedro e São Paulo',
    'São Roque González e companheiros',
    'Santo Edmundo',
    'Apresentação de Nossa Senhora',
    'Santa Cecília',
    'São Clemente I e São Columbano',
    'Santo André Dung-Lac e companheiros',
    'Santa Catarina de Alexandria',
    'São Leonardo de Porto Maurício',
    'Nossa Senhora das Graças',
    'São Tiago das Marcas',
    'São Saturnino',
    'Santo André Apóstolo',
  ],
  12: [
    'Santo Elói',
    'Santa Bibiana',
    'São Francisco Xavier',
    'São João Damasceno',
    'São Sabas',
    'São Nicolau',
    'Santo Ambrósio',
    'Imaculada Conceição de Nossa Senhora',
    'São Juan Diego',
    'Nossa Senhora de Loreto',
    'São Dâmaso I',
    'Nossa Senhora de Guadalupe',
    'Santa Luzia',
    'São João da Cruz',
    'Santa Cristiana',
    'Santa Adelaide',
    'São Lázaro',
    'São Maláquias',
    'Santo Urbano V',
    'São Domingos de Silos',
    'São Pedro Canísio',
    'Santa Francisca Xavier Cabrini',
    'São João Câncio',
    'Santos antepassados de Cristo',
    'Natividade do Senhor',
    'Santo Estêvão',
    'São João Evangelista',
    'Santos Inocentes',
    'São Tomás Becket',
    'São Sabino',
    'São Silvestre I',
  ],
}

const CALENDAR_DETAILS: Record<string, Partial<CalendarSaint>> = {
  [normalizeText('São Basílio Magno e São Gregório Nazianzeno')]: {
    rank: 'Memória',
    summary:
      'Bispos e doutores da Igreja, testemunhas da fé nicena e da profundidade teológica dos Padres capadócios.',
    theme: 'Doutrina trinitária e vida episcopal',
    aliases: ['Basílio de Cesareia', 'Gregório Nazianzeno'],
  },
  [normalizeText('São Gregório de Nissa')]: {
    summary:
      'Padre capadócio ligado à defesa da fé nicena, à teologia espiritual e à contemplação do mistério de Deus.',
    theme: 'Mística, Escritura e teologia capadócia',
    aliases: ['Gregório de Nissa'],
  },
  [normalizeText('Santo Hilário de Poitiers')]: {
    summary:
      'Doutor da Igreja e defensor da fé trinitária contra o arianismo.',
    theme: 'Trindade e ortodoxia nicena',
    aliases: ['Hilário de Poitiers'],
  },
  [normalizeText('Santo Atanásio')]: {
    rank: 'Memória',
    summary:
      'Bispo de Alexandria, doutor da Igreja e uma das grandes vozes da fé na divindade de Cristo.',
    theme: 'Cristologia e defesa da fé nicena',
    aliases: ['Atanásio', 'Santo Atanásio de Alexandria'],
  },
  [normalizeText('São Justino')]: {
    rank: 'Memória',
    summary:
      'Mártir e apologista cristão antigo, importante ponte entre filosofia, Escritura e testemunho público da fé.',
    theme: 'Apologética e martírio',
    aliases: ['Justino Mártir'],
  },
  [normalizeText('São Carlos Lwanga e companheiros')]: {
    rank: 'Memória',
    summary:
      'Mártires de Uganda, jovens cristãos que confessaram a fé em Cristo diante da perseguição do rei Mwanga II.',
    theme: 'Martírio, juventude cristã e pureza',
    aliases: [
      'Carlos Lwanga',
      'São Carlos Lwanga',
      'Mártires de Uganda',
      'Mártires Ugandenses',
      'Carlos Lwanga e companheiros',
    ],
  },
  [normalizeText('Santo Efrém')]: {
    summary:
      'Diácono, poeta e doutor da Igreja, conhecido pela catequese em forma de hinos e pela riqueza espiritual siríaca.',
    theme: 'Catequese poética e tradição siríaca',
    aliases: ['Efrém da Síria', 'Santo Efrém da Síria'],
  },
  [normalizeText('São Cirilo de Alexandria')]: {
    summary:
      'Bispo de Alexandria, doutor da Igreja e referência decisiva na teologia cristológica do século V.',
    theme: 'Cristologia e tradição alexandrina',
    aliases: ['Cirilo de Alexandria'],
  },
  [normalizeText('Santo Irineu de Lião')]: {
    rank: 'Memória',
    summary:
      'Padre da Igreja, bispo e mártir, conhecido por sua defesa da fé apostólica contra as heresias.',
    theme: 'Tradição apostólica e unidade da fé',
    aliases: ['Irineu de Lião', 'Santo Irineu'],
  },
  [normalizeText('Santo Agostinho')]: {
    rank: 'Memória',
    summary:
      'Bispo de Hipona e doutor da Igreja, referência central para a graça, a Trindade, a Escritura e a vida interior.',
    theme: 'Graça, conversão e doutrina cristã',
    aliases: ['Agostinho', 'Agostinho de Hipona', 'Santo Agostinho de Hipona'],
  },
  [normalizeText('São Gregório Magno')]: {
    rank: 'Memória',
    summary:
      'Papa, doutor da Igreja e pastor cuja obra une governo eclesial, espiritualidade e leitura das Escrituras.',
    theme: 'Pastoral, Escritura e governo da Igreja',
    aliases: ['Gregório Magno', 'São Gregório I'],
  },
  [normalizeText('São João Crisóstomo')]: {
    rank: 'Memória',
    summary:
      'Bispo de Constantinopla, doutor da Igreja e mestre da pregação bíblica e moral.',
    theme: 'Pregação, Escritura e vida moral',
    aliases: ['João Crisóstomo', 'São João Crisóstomo'],
  },
  [normalizeText('São Cornélio e São Cipriano')]: {
    rank: 'Memória',
    summary:
      'Pastores e mártires ligados à disciplina e à unidade da Igreja em tempos de perseguição.',
    theme: 'Unidade e disciplina eclesial',
    aliases: ['Cipriano de Cartago', 'São Cipriano de Cartago'],
  },
  [normalizeText('São Jerônimo')]: {
    rank: 'Memória',
    summary:
      'Presbítero, doutor da Igreja e grande mestre da tradução e interpretação das Escrituras.',
    theme: 'Escritura, tradução e estudo',
    aliases: ['Jerônimo', 'São Jerônimo'],
  },
  [normalizeText('Santo Ambrósio')]: {
    rank: 'Memória',
    summary:
      'Bispo de Milão, doutor da Igreja e referência em catequese sacramental e vida pastoral.',
    theme: 'Sacramentos, catequese e episcopado',
    aliases: ['Ambrósio', 'Santo Ambrósio de Milão'],
  },
  [normalizeText('São Tomás de Aquino')]: {
    rank: 'Memória',
    summary:
      'Presbítero dominicano e doutor da Igreja, referência maior da teologia escolástica.',
    theme: 'Teologia, filosofia e doutrina',
    aliases: ['Tomás de Aquino', 'Santo Tomás de Aquino'],
  },
  [normalizeText('São João Damasceno')]: {
    summary:
      'Doutor da Igreja e testemunha da tradição oriental, ligado à defesa das imagens sagradas.',
    theme: 'Teologia oriental e imagens sagradas',
    aliases: ['João Damasceno'],
  },
}

const COMMON_HAGIOGRAPHY_SOURCES: SaintSource[] = [
  { label: 'Martirológio Romano' },
  { label: 'Santos de cada dia II - José Leite, S.J. (org.)' },
  { label: 'Canção Nova - Santo do Dia', url: 'https://santo.cancaonova.com/' },
  { label: 'Vatican News - Santo do Dia', url: 'https://www.vaticannews.va/pt/santo-do-dia.html' },
  { label: 'Arquisp' },
  { label: 'Franciscanos.org' },
]

const HAGIOGRAPHY_DETAILS: Record<string, SaintHagiography> = {
  [normalizeText('São Marcelino e São Pedro')]: {
    storyTitle: 'Mártires escondidos que a Igreja nunca esqueceu',
    history: [
      'Marcelino, presbítero romano, e Pedro, exorcista, viveram no começo do século IV, quando a perseguição de Diocleciano procurava sufocar a presença cristã em Roma. A tradição recorda que, mesmo presos, continuaram anunciando Cristo e sustentando a fé de outros cristãos.',
      'Na prisão, seu testemunho alcançou o ambiente dos carcereiros e das famílias que sofriam. As antigas narrativas ligam os dois santos à conversão de pessoas próximas ao cárcere, mostrando que a evangelização cristã também floresceu nos lugares mais escondidos.',
      'Condenados à morte, foram levados a um bosque para que o martírio ficasse oculto. A memória transmitida por São Dâmaso afirma que foram obrigados a preparar suas próprias sepulturas e depois decapitados, por volta do ano 304.',
    ],
    witness: [
      'Fidelidade no cárcere e diante da ameaça de morte.',
      'Evangelização silenciosa, feita onde a Providência os colocava.',
      'Testemunho sacerdotal e ministerial em favor dos perseguidos.',
    ],
    devotion: [
      'Uma cristã chamada Lucila é ligada à recuperação e ao sepultamento digno de seus corpos.',
      'A memória dos mártires foi preservada na Via Labicana, nas catacumbas chamadas ad Duas Lauros.',
      'Seus nomes entraram no Cânon Romano, sinal de veneração antiga e litúrgica.',
    ],
    virtues: ['coragem', 'evangelização', 'fidelidade', 'caridade pastoral'],
    prayer:
      'Senhor Jesus, que destes a São Marcelino e São Pedro força para confessar a fé mesmo quando tudo parecia escondido, concedei-nos coragem para vos anunciar com caridade, firmeza e humildade. Amém.',
    otherCelebrations: [
      'Santos Potino, Blandina e companheiros mártires de Lião († 177)',
      'Santo Erasmo, bispo e mártir († c. 303)',
      'São Nicéforo, bispo de Constantinopla († 828)',
      'Beato Sadoc e companheiros mártires († 1260)',
    ],
    sources: [
      { label: 'Martirológio Romano' },
      { label: 'Canção Nova - São Marcelino e São Pedro', url: 'https://santo.cancaonova.com/' },
      {
        label: 'Vatican News - SS. Marcelino e Pedro',
        url: 'https://www.vaticannews.va/pt/santo-do-dia/06/02/ss--marcelino--presbitero--e-pedro--exorcista--martires--na-via-.html',
      },
      { label: 'Santos de cada dia II - José Leite, S.J. (org.)' },
    ],
  },
  [normalizeText('São Carlos Lwanga e companheiros')]: {
    storyTitle: 'Jovens mártires de Uganda que permaneceram firmes até o fogo',
    history: [
      'Carlos Lwanga viveu no reino de Buganda, na atual Uganda, no final do século XIX. A fé cristã havia chegado à região por meio de missionários católicos e anglicanos, num contexto complexo de tensões políticas, disputas culturais e presença europeia na África. Entre os jovens servidores da corte real, a mensagem de Cristo começou a criar raízes de modo rápido e profundo.',
      'Na corte do rei Mwanga II, Carlos Lwanga servia como responsável por jovens pajens. Depois de acolher a fé católica, tornou-se referência para outros rapazes convertidos ou catecúmenos. Ele os ajudava a rezar, instruía-os na fé, protegia sua consciência cristã e sustentava especialmente os mais novos diante das pressões morais e religiosas do ambiente palaciano.',
      'A perseguição se intensificou quando o rei passou a ver a fé cristã como ameaça à sua autoridade. A recusa dos jovens em abandonar a oração, a castidade e a fidelidade a Cristo provocou a ira do soberano. Antes do martírio, Carlos fortaleceu os companheiros e, segundo a tradição, batizou aqueles que ainda eram catecúmenos, preparando-os para confessar Cristo até o fim.',
      'Os condenados foram conduzidos a Namugongo, sofrendo humilhações e violência no caminho. Em 3 de junho de 1886, Carlos Lwanga foi morto pelo fogo, e outros companheiros também consumaram o martírio. A tentativa de apagar a fé produziu o contrário: a memória dos mártires de Uganda tornou-se semente de evangelização para a África e para toda a Igreja.',
      'A Igreja venera São Carlos Lwanga e seus companheiros como testemunhas da juventude cristã, da pureza, da coragem e da fidelidade ao Evangelho. Beatificados por Bento XV em 1920 e canonizados por São Paulo VI em 1964, eles são recordados no Calendário Romano em 3 de junho. Carlos Lwanga foi também apresentado por Pio XI como patrono da juventude africana cristã.',
    ],
    witness: [
      'Confessaram publicamente a fé quando rezar e permanecer cristão significava colocar a própria vida em risco.',
      'São Carlos Lwanga cuidou dos mais jovens, fortaleceu os catecúmenos e protegeu a dignidade cristã dos companheiros.',
      'O martírio em Namugongo mostra uma fé jovem, consciente e perseverante, capaz de resistir ao medo e à violência.',
      'A memória dos mártires une católicos e anglicanos no testemunho de Cristo, frequentemente chamado de ecumenismo do sangue.',
    ],
    devotion: [
      'A celebração de 3 de junho recorda os vinte e dois mártires católicos de Uganda e, de modo amplo, a fecundidade espiritual daquele testemunho.',
      'Namugongo tornou-se lugar de peregrinação e oração, com santuário dedicado aos mártires de Uganda.',
      'A canonização por São Paulo VI, durante o Concílio Vaticano II, apresentou estes mártires como sinal da vitalidade da Igreja africana.',
      'Sua história é especialmente ligada à juventude, à perseverança na oração, à castidade e à coragem diante de ambientes hostis à fé.',
    ],
    virtues: ['martírio', 'pureza', 'juventude cristã', 'coragem', 'oração', 'fidelidade'],
    prayer:
      'Senhor Jesus Cristo, que sustentastes São Carlos Lwanga e seus companheiros no amor à fé, à oração e à pureza, dai-nos coragem para vos confessar sem medo, proteger os mais frágeis e permanecer fiéis à vossa Igreja mesmo nas provações. Amém.',
    otherCelebrations: [
      'São Cecílio, presbítero em Cartago, ligado à conversão de São Cipriano († c. 211)',
      'Santo Hilário, venerado como primeiro bispo de Carcassonne († s. VI)',
      'Santa Clotilde, rainha dos francos, cuja oração marcou a conversão de Clóvis († 545)',
      'São Lifardo, presbítero e eremita na região de Orléans († s. VI)',
      'Santa Oliva, virgem venerada em Anagni († s. VI/VII)',
      'São Kevin ou Coemgen, abade de Glendalough, na Irlanda († 622)',
      'São Gens, bispo de Clermont († c. 650)',
      'Santo Isaac de Córdova, monge e mártir († 851)',
      'São Davino, peregrino armênio na Itália († 1051)',
      'São Morando, monge de Cluny († 1115)',
      'Beato André Caccióli, presbítero franciscano († 1254)',
      'São Cono, monge na Itália meridional († s. XIII)',
      'Beato Francisco Ingleby, presbítero e mártir na Inglaterra († 1580)',
      'São João Grande, religioso hospitaleiro († 1600)',
      'Beato Carlos Renato Collas de Bignon, presbítero e mártir na Revolução Francesa († 1794)',
      'São Pedro Dong, pai de família e mártir no Vietnã († 1862)',
      'Beato José Oddi, religioso franciscano († 1919)',
      'Falecimento de São João XXIII, Papa; memória litúrgica em 11 de outubro († 1963)',
    ],
    sources: [
      { label: 'Martirológio Romano' },
      {
        label: 'Canção Nova - São Carlos Lwanga e companheiros',
        url: 'https://santo.cancaonova.com/santo/sao-carlos-lwanga-e-companheiros-martires/',
      },
      {
        label: 'Vatican News - SS. Carlos Lwanga e Companheiros',
        url: 'https://www.vaticannews.va/pt/santo-do-dia/06/03/ss--carlos-lwanga-e-companheiros--martires-de-uganda.html',
      },
      {
        label: 'Vatican News - Mártires de Uganda e ecumenismo do sangue',
        url: 'https://www.vaticannews.va/pt/igreja/news/2022-06/martires-uganda-3-de-junho-ecumenismo.html',
      },
      { label: 'Santos de cada dia II - José Leite, S.J. (org.)' },
      { label: 'Arquisp' },
    ],
  },
  [normalizeText('Santo Agostinho')]: {
    storyTitle: 'Da busca inquieta à inteligência humilde da fé',
    history: [
      'Agostinho nasceu no norte da África romana e atravessou uma longa busca intelectual e espiritual antes de receber o batismo. Sua conversão, marcada pela oração de Santa Mônica e pela pregação de Santo Ambrósio, tornou-se uma das grandes narrativas cristãs sobre graça e liberdade.',
      'Como bispo de Hipona, pregou, debateu, escreveu e serviu a Igreja em meio a crises doutrinais e políticas. Suas obras unem experiência interior, leitura das Escrituras e defesa da fé católica.',
    ],
    witness: ['Conversão perseverante.', 'Amor às Escrituras.', 'Defesa da graça e da unidade da Igreja.'],
    devotion: ['Doutor da Igreja.', 'Referência central para teologia, filosofia e espiritualidade cristã.'],
    virtues: ['conversão', 'humildade intelectual', 'amor à verdade'],
    prayer:
      'Senhor, pela intercessão de Santo Agostinho, dai-nos um coração inquieto pela verdade e humilde diante da vossa graça. Amém.',
    otherCelebrations: [],
    sources: COMMON_HAGIOGRAPHY_SOURCES,
  },
  [normalizeText('São João Crisóstomo')]: {
    storyTitle: 'A palavra ardente a serviço do Evangelho',
    history: [
      'João Crisóstomo foi bispo de Constantinopla e tornou-se célebre pela força de sua pregação bíblica. Sua palavra unia beleza literária, exigência moral e atenção aos pobres.',
      'Sofreu tensões políticas e eclesiais, inclusive o exílio, mas permaneceu como uma das grandes vozes da tradição oriental.',
    ],
    witness: ['Pregação clara.', 'Coragem diante do poder.', 'Amor à Escritura.'],
    devotion: ['Doutor da Igreja.', 'Mestre da homilia e da interpretação pastoral de São Paulo.'],
    virtues: ['coragem', 'eloquência sagrada', 'amor aos pobres'],
    prayer:
      'Senhor, ensinai-nos, com São João Crisóstomo, a falar da fé com verdade, caridade e coragem. Amém.',
    otherCelebrations: [],
    sources: COMMON_HAGIOGRAPHY_SOURCES,
  },
  [normalizeText('São Jerônimo')]: {
    storyTitle: 'A Escritura estudada com rigor e reverência',
    history: [
      'Jerônimo dedicou a vida ao estudo das Escrituras, às línguas bíblicas e à transmissão fiel do texto sagrado. Sua tradução latina da Bíblia marcou profundamente a Igreja ocidental.',
      'A austeridade de sua vida e o vigor de suas controvérsias revelam um santo apaixonado pela Palavra de Deus.',
    ],
    witness: ['Estudo das línguas bíblicas.', 'Amor à Palavra de Deus.', 'Vida ascética.'],
    devotion: ['Doutor da Igreja.', 'Patrono dos estudos bíblicos.'],
    virtues: ['estudo', 'fidelidade textual', 'ascese'],
    prayer:
      'Senhor, pela intercessão de São Jerônimo, dai-nos amor sincero pelas Escrituras e disciplina para estudá-las com fidelidade. Amém.',
    otherCelebrations: [],
    sources: COMMON_HAGIOGRAPHY_SOURCES,
  },
}

export const SAINT_WORK_PROFILES: SaintWorkProfile[] = [
  {
    name: 'São Cipriano de Cartago',
    title: 'Bispo, mártir e Padre latino',
    century: 'Séc. III',
    collection: 'PL 4',
    summary: 'Unidade da Igreja, disciplina sacramental e testemunho martirial.',
    aliases: ['Cipriano', 'Cipriano de Cartago', 'São Cipriano', 'São Cipriano de Cartago'],
  },
  {
    name: 'Santo Agostinho de Hipona',
    title: 'Bispo de Hipona e Doutor da Igreja',
    century: 'Séc. IV-V',
    collection: 'PL 32-46',
    summary: 'Graça, Trindade, Escritura, vida interior e controvérsias pastorais.',
    aliases: ['Agostinho', 'Santo Agostinho', 'Agostinho de Hipona'],
  },
  {
    name: 'São João Crisóstomo',
    title: 'Bispo de Constantinopla e Doutor da Igreja',
    century: 'Séc. IV',
    collection: 'PG 47-64',
    summary: 'Homilias bíblicas, moral cristã e comentário paulino.',
    aliases: ['João Crisóstomo', 'São João Crisóstomo'],
  },
  {
    name: 'São Jerônimo',
    title: 'Presbítero e Doutor da Igreja',
    century: 'Séc. IV',
    collection: 'PL 22-30',
    summary: 'Escritura, tradução, comentário bíblico e controvérsia teológica.',
    aliases: ['Jerônimo', 'São Jerônimo'],
  },
  {
    name: 'Santo Ambrósio de Milão',
    title: 'Bispo de Milão e Doutor da Igreja',
    century: 'Séc. IV',
    collection: 'PL 14-17',
    summary: 'Catequese sacramental, mistérios, penitência e vida pastoral.',
    aliases: ['Ambrósio', 'Santo Ambrósio', 'Santo Ambrósio de Milão'],
  },
  {
    name: 'São Leão Magno',
    title: 'Papa e Doutor da Igreja',
    century: 'Séc. V',
    collection: 'PL 54-56',
    summary: 'Cristologia, primado romano e pregação pastoral.',
    aliases: ['Leão Magno', 'São Leão Magno', 'Papa Leão Magno'],
  },
  {
    name: 'São Gregório Magno',
    title: 'Papa e Doutor da Igreja',
    century: 'Séc. VI',
    collection: 'PL 75-79',
    summary: 'Regra pastoral, cartas e governo espiritual da Igreja.',
    aliases: ['Gregório Magno', 'São Gregório Magno', 'São Gregório I'],
  },
  {
    name: 'Santo Atanásio',
    title: 'Bispo de Alexandria e Doutor da Igreja',
    century: 'Séc. IV',
    collection: 'PG 25-28',
    summary: 'Cristologia, Encarnação do Verbo e defesa da fé nicena.',
    aliases: ['Atanásio', 'Santo Atanásio', 'Santo Atanásio de Alexandria'],
  },
  {
    name: 'Santo Irineu de Lião',
    title: 'Bispo, mártir e Padre da Igreja',
    century: 'Séc. II',
    collection: 'PG 7',
    summary: 'Tradição apostólica, regra da fé e combate às heresias.',
    aliases: ['Irineu', 'Irineu de Lião', 'Santo Irineu', 'Santo Irineu de Lião'],
  },
  {
    name: 'São Basílio de Cesareia',
    title: 'Padre capadócio e Doutor da Igreja',
    century: 'Séc. IV',
    collection: 'PG 29-32',
    summary: 'Espírito Santo, vida monástica e teologia capadócia.',
    aliases: ['Basílio', 'Basílio de Cesareia', 'São Basílio', 'São Basílio de Cesareia'],
  },
  {
    name: 'São Gregório de Nissa',
    title: 'Padre capadócio',
    century: 'Séc. IV',
    collection: 'PG 44-46',
    summary: 'Vida espiritual, contemplação e exegese teológica.',
    aliases: ['Gregório de Nissa', 'São Gregório de Nissa'],
  },
  {
    name: 'Santo Hilário de Poitiers',
    title: 'Bispo e Doutor da Igreja',
    century: 'Séc. IV',
    collection: 'PL 9-10',
    summary: 'Defesa da fé trinitária e combate ao arianismo.',
    aliases: ['Hilário', 'Hilário de Poitiers', 'Santo Hilário de Poitiers'],
  },
  {
    name: 'Orígenes',
    title: 'Escritor e exegeta alexandrino',
    century: 'Séc. III',
    collection: 'PG 11-17',
    summary: 'Exegese, apologética e teologia cristã antiga.',
    aliases: ['Orígenes', 'Origenes'],
  },
  {
    name: 'Tertuliano',
    title: 'Escritor cristão latino',
    century: 'Séc. II-III',
    collection: 'PL 1-2',
    summary: 'Apologética latina e linguagem teológica antiga.',
    aliases: ['Tertuliano'],
  },
  {
    name: 'Novaciano',
    title: 'Presbítero e escritor cristão',
    century: 'Séc. III',
    collection: 'PL 3',
    summary: 'Trindade, disciplina e escritos éticos.',
    aliases: ['Novaciano'],
  },
  {
    name: 'São Tomás de Aquino',
    title: 'Presbítero dominicano e Doutor da Igreja',
    century: 'Séc. XIII',
    collection: '—',
    summary: 'Teologia escolástica, filosofia cristã e síntese doutrinal.',
    aliases: ['Tomás de Aquino', 'Santo Tomás de Aquino', 'São Tomás de Aquino'],
  },
]

export function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/sant[oa]s?\s+/g, '')
    .replace(/sao\s+/g, '')
    .replace(/beata?s?\s+/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function ptBrDateParts(date: Date): { day: number; month: number; year: number } {
  const parts = new Intl.DateTimeFormat('pt-BR', {
    timeZone: 'America/Sao_Paulo',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).formatToParts(date)

  const day = Number(parts.find(part => part.type === 'day')?.value ?? '1')
  const month = Number(parts.find(part => part.type === 'month')?.value ?? '1')
  const year = Number(parts.find(part => part.type === 'year')?.value ?? date.getFullYear())
  return { day, month, year }
}

function aliasesFromName(name: string): string[] {
  return name
    .split(/,| e |;|\//)
    .map(part => part.trim())
    .filter(Boolean)
}

function buildFallbackHagiography(name: string, detail: Partial<CalendarSaint>): SaintHagiography {
  const theme = detail.theme ?? 'santidade cotidiana e fidelidade à Igreja'
  const summary =
    detail.summary ??
    'A tradição litúrgica conserva esta memória como parte do santoral recebido pela Igreja.'

  return {
    storyTitle: `${name}: memória litúrgica e testemunho cristão`,
    history: [
      summary,
      `No calendário dos santos, a celebração de ${name} é recebida como memória de uma vida concreta configurada por Cristo. A Igreja conserva estas comemorações para que cada geração aprenda a fé não apenas por conceitos, mas também pela história de homens e mulheres que viveram o Evangelho em circunstâncias reais.`,
      `A tradição hagiográfica lê cada santo a partir de sua vocação própria: martírio, vida monástica, ministério pastoral, virgindade consagrada, caridade, defesa da doutrina, missão ou penitência. Nesta memória, o eixo espiritual indicado é ${theme}.`,
      'Quando houver fontes biográficas específicas verificadas, o Vera.Fidei apresenta a vida em forma mais extensa, com contexto histórico, virtudes, devoção litúrgica e obras vinculadas no acervo.',
    ],
    witness: [
      `Testemunho de ${theme}.`,
      'Vida cristã lida em comunhão com o calendário romano, o Martirológio e a tradição hagiográfica da Igreja.',
      'Memória espiritual voltada à oração, ao estudo e à imitação das virtudes.',
    ],
    devotion: [
      'A celebração diária ajuda a rezar com a Igreja e a aprender a fé pela vida concreta dos santos.',
      'As fontes hagiográficas e litúrgicas são usadas como ponto de partida para organizar a memória do santo no Vera.Fidei.',
      'Quando houver obras ou fontes primárias no acervo, o vínculo direto aparece automaticamente para estudo.',
    ],
    virtues: [theme, 'perseverança', 'comunhão com a Igreja'],
    prayer:
      `Senhor, que a memória de ${name} nos ajude a amar mais a vossa Igreja, viver com fidelidade e buscar a santidade nas obras de cada dia. Amém.`,
    otherCelebrations: [],
    sources: COMMON_HAGIOGRAPHY_SOURCES,
  }
}

export function getRomanSaintForDate(date = new Date()): CalendarSaint {
  const { day, month } = ptBrDateParts(date)
  const name = MONTH_SAINTS[month]?.[day - 1] ?? 'Todos os Santos'
  const detail = CALENDAR_DETAILS[normalizeText(name)] ?? {}

  return {
    key: `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`,
    dateLabel: `${String(day).padStart(2, '0')}/${String(month).padStart(2, '0')}`,
    name,
    rank: detail.rank ?? 'Santo do dia',
    summary:
      detail.summary ??
      'Memória do santoral católico organizada por data para acompanhar oração, estudo e consulta às fontes do Vera.Fidei.',
    theme: detail.theme ?? 'Santidade cotidiana e fidelidade à Igreja',
    aliases: detail.aliases ?? aliasesFromName(name),
    hagiography:
      HAGIOGRAPHY_DETAILS[normalizeText(name)] ??
      buildFallbackHagiography(name, detail),
  }
}

export function getUpcomingRomanSaints(count = 5): CalendarSaint[] {
  const today = new Date()
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(today)
    date.setDate(today.getDate() + index)
    return getRomanSaintForDate(date)
  })
}
