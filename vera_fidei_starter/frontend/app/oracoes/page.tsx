import BrandHeader from '@/components/BrandHeader'
import OracoesView from '@/components/oracoes/OracoesView'

export const revalidate = 43200

type PrayerVersion = {
  lang: 'Português' | 'Latim' | 'Inglês'
  text: string
}

type PrayerItem = {
  id: string
  title: string
  modified?: string
  source?: string
  versions: PrayerVersion[]
  note?: string
}

type PrayerGroup = {
  title: string
  description: string
  code: string
  items: PrayerItem[]
}

type RemotePrayer = {
  id?: number | string
  dia?: string
  modified?: string
  titulo?: string
  texto?: string
}

type RemotePrayerResponse = {
  oracoes?: RemotePrayer[]
}

const CANCAO_NOVA_PRAYERS_URL = 'https://liturgia.cancaonova.com/pb/json-oracoes/'

const GROUP_META = [
  {
    code: 'MARIA',
    title: 'Orações Marianas',
    description: 'Devoções a Nossa Senhora, rosário, consagrações e invocações marianas.',
  },
  {
    code: 'DIV',
    title: 'Orações Diversas',
    description: 'Intenções comuns da vida cristã, família, cura, trabalho, paz e conversão.',
  },
  {
    code: 'JOSE',
    title: 'São José',
    description: 'Orações, consagrações, terços, tríduos e proteção do Patriarca São José.',
  },
  {
    code: 'EUCA',
    title: 'Orações Eucarísticas',
    description: 'Adoração, comunhão espiritual, Missa, Sangue de Cristo e Santíssimo Sacramento.',
  },
  {
    code: 'ESP',
    title: 'Orações ao Espírito Santo',
    description: 'Pentecostes, discernimento, dons, novenas e súplicas ao Paráclito.',
  },
  {
    code: 'NOV',
    title: 'Novenas',
    description: 'Novenas, tríduos, decenários e roteiros prolongados de intercessão.',
  },
  {
    code: 'VIACR',
    title: 'Via Sacra',
    description: 'Meditações da Paixão de Cristo, Cruz e estações da Via-Sacra.',
  },
  {
    code: 'SEQ',
    title: 'Sequências Litúrgicas',
    description: 'Sequências, hinos litúrgicos e textos ligados ao ano da Igreja.',
  },
  {
    code: 'DOUT',
    title: 'Orando com os Doutores da Igreja',
    description: 'Orações e textos espirituais ligados aos Padres, Doutores e mestres da fé.',
  },
  {
    code: 'DIARIA',
    title: 'Roteiro de Orações Diárias',
    description: 'Manhã, noite, exame de consciência, contrição e oferecimento do dia.',
  },
  {
    code: 'BIBLIA',
    title: 'Para ler a Bíblia',
    description: 'Orações, métodos e preparação para leitura orante das Escrituras.',
  },
  {
    code: 'BASE',
    title: 'Principais Orações Diárias',
    description: 'Orações fundamentais da vida católica, fórmulas comuns e profissão de fé.',
  },
  {
    code: 'SANTOS',
    title: 'Orações aos Santos',
    description: 'Intercessão dos santos, anjos, arcanjos e protetores espirituais.',
  },
  {
    code: 'SANTAS',
    title: 'Orações às Santas',
    description: 'Intercessão das santas, beatas e modelos femininos de santidade.',
  },
] as const

type GroupCode = typeof GROUP_META[number]['code']

const fallbackPrayerGroups: PrayerGroup[] = [
  {
    title: 'Principais Orações Diárias',
    description: 'Orações fundamentais da vida católica.',
    code: 'BASE',
    items: [
      {
        id: 'fallback-sinal-da-cruz',
        title: 'Sinal da Cruz',
        source: 'Vera.Fidei',
        versions: [
          {
            lang: 'Português',
            text: 'Pelo sinal da santa cruz, livrai-nos, Deus, nosso Senhor, dos nossos inimigos. Em nome do Pai, e do Filho, e do Espírito Santo. Amém.',
          },
          {
            lang: 'Latim',
            text: 'In nomine Patris, et Filii, et Spiritus Sancti. Amen.',
          },
          {
            lang: 'Inglês',
            text: 'By the sign of the holy Cross, deliver us from our enemies, O Lord our God. In the name of the Father, and of the Son, and of the Holy Spirit. Amen.',
          },
        ],
      },
      {
        id: 'fallback-pai-nosso',
        title: 'Pai Nosso',
        source: 'Vera.Fidei',
        versions: [
          {
            lang: 'Português',
            text: 'Pai nosso, que estais nos céus, santificado seja o vosso nome; venha a nós o vosso reino; seja feita a vossa vontade, assim na terra como no céu. O pão nosso de cada dia nos dai hoje; perdoai-nos as nossas ofensas, assim como nós perdoamos a quem nos tem ofendido; e não nos deixeis cair em tentação, mas livrai-nos do mal. Amém.',
          },
          {
            lang: 'Latim',
            text: 'Pater noster, qui es in caelis, sanctificetur nomen tuum; adveniat regnum tuum; fiat voluntas tua, sicut in caelo et in terra. Panem nostrum quotidianum da nobis hodie; et dimitte nobis debita nostra, sicut et nos dimittimus debitoribus nostris; et ne nos inducas in tentationem, sed libera nos a malo. Amen.',
          },
          {
            lang: 'Inglês',
            text: 'Our Father, who art in heaven, hallowed be thy name; thy kingdom come; thy will be done on earth as it is in heaven. Give us this day our daily bread; and forgive us our trespasses, as we forgive those who trespass against us; and lead us not into temptation, but deliver us from evil. Amen.',
          },
        ],
      },
      {
        id: 'fallback-ave-maria',
        title: 'Ave Maria',
        source: 'Vera.Fidei',
        versions: [
          {
            lang: 'Português',
            text: 'Ave Maria, cheia de graça, o Senhor é convosco. Bendita sois vós entre as mulheres, e bendito é o fruto do vosso ventre, Jesus. Santa Maria, Mãe de Deus, rogai por nós, pecadores, agora e na hora de nossa morte. Amém.',
          },
          {
            lang: 'Latim',
            text: 'Ave Maria, gratia plena, Dominus tecum; benedicta tu in mulieribus, et benedictus fructus ventris tui, Iesus. Sancta Maria, Mater Dei, ora pro nobis peccatoribus, nunc et in hora mortis nostrae. Amen.',
          },
          {
            lang: 'Inglês',
            text: 'Hail Mary, full of grace, the Lord is with thee. Blessed art thou among women, and blessed is the fruit of thy womb, Jesus. Holy Mary, Mother of God, pray for us sinners, now and at the hour of our death. Amen.',
          },
        ],
      },
    ],
  },
]

function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’'`´]/g, '')
    .toLowerCase()
}

function includesAny(text: string, terms: string[]): boolean {
  return terms.some(term => text.includes(term))
}

const EXTRA_TRADITIONAL_VERSIONS: Record<string, PrayerVersion[]> = {
  'persignacao': [
    { lang: 'Latim', text: 'Per signum sanctae crucis de inimicis nostris libera nos, Deus noster. In nomine Patris, et Filii, et Spiritus Sancti. Amen.' },
    { lang: 'Inglês', text: 'By the sign of the holy Cross, deliver us from our enemies, O Lord our God. In the name of the Father, and of the Son, and of the Holy Spirit. Amen.' },
  ],
  'sinal da cruz': [
    { lang: 'Latim', text: 'In nomine Patris, et Filii, et Spiritus Sancti. Amen.' },
    { lang: 'Inglês', text: 'In the name of the Father, and of the Son, and of the Holy Spirit. Amen.' },
  ],
  'pai-nosso': [
    { lang: 'Latim', text: 'Pater noster, qui es in caelis, sanctificetur nomen tuum; adveniat regnum tuum; fiat voluntas tua, sicut in caelo et in terra. Panem nostrum quotidianum da nobis hodie; et dimitte nobis debita nostra, sicut et nos dimittimus debitoribus nostris; et ne nos inducas in tentationem, sed libera nos a malo. Amen.' },
    { lang: 'Inglês', text: 'Our Father, who art in heaven, hallowed be thy name; thy kingdom come; thy will be done on earth as it is in heaven. Give us this day our daily bread; and forgive us our trespasses, as we forgive those who trespass against us; and lead us not into temptation, but deliver us from evil. Amen.' },
  ],
  'ave-maria': [
    { lang: 'Latim', text: 'Ave Maria, gratia plena, Dominus tecum; benedicta tu in mulieribus, et benedictus fructus ventris tui, Iesus. Sancta Maria, Mater Dei, ora pro nobis peccatoribus, nunc et in hora mortis nostrae. Amen.' },
    { lang: 'Inglês', text: 'Hail Mary, full of grace, the Lord is with thee. Blessed art thou among women, and blessed is the fruit of thy womb, Jesus. Holy Mary, Mother of God, pray for us sinners, now and at the hour of our death. Amen.' },
  ],
  'gloria ao pai': [
    { lang: 'Latim', text: 'Gloria Patri, et Filio, et Spiritui Sancto. Sicut erat in principio, et nunc, et semper, et in saecula saeculorum. Amen.' },
    { lang: 'Inglês', text: 'Glory be to the Father, and to the Son, and to the Holy Spirit. As it was in the beginning, is now, and ever shall be, world without end. Amen.' },
  ],
  'santo anjo do senhor': [
    { lang: 'Latim', text: 'Angele Dei, qui custos es mei, me tibi commissum pietate superna, illumina, custodi, rege et guberna. Amen.' },
    { lang: 'Inglês', text: 'Angel of God, my guardian dear, to whom God’s love commits me here, ever this day be at my side, to light and guard, to rule and guide. Amen.' },
  ],
  'alma de cristo': [
    { lang: 'Latim', text: 'Anima Christi, sanctifica me. Corpus Christi, salva me. Sanguis Christi, inebria me. Aqua lateris Christi, lava me. Passio Christi, conforta me. O bone Iesu, exaudi me. Intra vulnera tua absconde me. Ne permittas me separari a te. Ab hoste maligno defende me. In hora mortis meae voca me, et iube me venire ad te, ut cum Sanctis tuis laudem te in saecula saeculorum. Amen.' },
    { lang: 'Inglês', text: 'Soul of Christ, sanctify me. Body of Christ, save me. Blood of Christ, inebriate me. Water from the side of Christ, wash me. Passion of Christ, strengthen me. O good Jesus, hear me. Within thy wounds hide me. Permit me not to be separated from thee. From the malicious enemy defend me. In the hour of my death call me, and bid me come unto thee, that with thy saints I may praise thee forever and ever. Amen.' },
  ],
  'salve-rainha': [
    { lang: 'Latim', text: 'Salve Regina, Mater misericordiae, vita, dulcedo et spes nostra, salve. Ad te clamamus, exsules filii Evae. Ad te suspiramus, gementes et flentes in hac lacrimarum valle. Eia ergo, advocata nostra, illos tuos misericordes oculos ad nos converte. Et Iesum, benedictum fructum ventris tui, nobis post hoc exsilium ostende. O clemens, o pia, o dulcis Virgo Maria.' },
    { lang: 'Inglês', text: 'Hail, Holy Queen, Mother of mercy, our life, our sweetness and our hope. To thee do we cry, poor banished children of Eve; to thee do we send up our sighs, mourning and weeping in this valley of tears. Turn then, most gracious advocate, thine eyes of mercy toward us; and after this our exile, show unto us the blessed fruit of thy womb, Jesus. O clement, O loving, O sweet Virgin Mary.' },
  ],
  'ato de contricao': [
    { lang: 'Latim', text: 'Deus meus, ex toto corde paenitet me omnium meorum peccatorum, eaque detestor, quia peccando non solum poenas a te iuste statutas promeritus sum, sed praesertim quia offendi te, summe bone ac dignum qui super omnia diligaris. Ideo firmiter propono, adiuvante gratia tua, de cetero me non peccaturum peccandique occasiones proximas fugiturum. Amen.' },
    { lang: 'Inglês', text: 'O my God, I am heartily sorry for having offended thee, and I detest all my sins because I dread the loss of heaven and the pains of hell, but most of all because they offend thee, my God, who art all good and deserving of all my love. I firmly resolve, with the help of thy grace, to confess my sins, to do penance, and to amend my life. Amen.' },
  ],
  'gloria a deus nas alturas': [
    { lang: 'Latim', text: 'Gloria in excelsis Deo, et in terra pax hominibus bonae voluntatis. Laudamus te, benedicimus te, adoramus te, glorificamus te, gratias agimus tibi propter magnam gloriam tuam. Domine Deus, Rex caelestis, Deus Pater omnipotens. Domine Fili unigenite, Iesu Christe. Domine Deus, Agnus Dei, Filius Patris. Qui tollis peccata mundi, miserere nobis. Qui tollis peccata mundi, suscipe deprecationem nostram. Qui sedes ad dexteram Patris, miserere nobis. Quoniam tu solus Sanctus, tu solus Dominus, tu solus Altissimus, Iesu Christe, cum Sancto Spiritu: in gloria Dei Patris. Amen.' },
    { lang: 'Inglês', text: 'Glory be to God on high, and on earth peace to men of good will. We praise thee, we bless thee, we adore thee, we glorify thee, we give thee thanks for thy great glory. O Lord God, heavenly King, God the Father almighty. O Lord Jesus Christ, the only begotten Son. O Lord God, Lamb of God, Son of the Father. Thou who takest away the sins of the world, have mercy on us. Thou who takest away the sins of the world, receive our prayer. Thou who sittest at the right hand of the Father, have mercy on us. For thou only art holy, thou only art the Lord, thou only art most high, O Jesus Christ, with the Holy Spirit, in the glory of God the Father. Amen.' },
  ],
  'oracao para antes das refeicoes': [
    { lang: 'Latim', text: 'Benedic, Domine, nos et haec tua dona, quae de tua largitate sumus sumpturi. Per Christum Dominum nostrum. Amen.' },
    { lang: 'Inglês', text: 'Bless us, O Lord, and these thy gifts, which we are about to receive from thy bounty. Through Christ our Lord. Amen.' },
  ],
  'lembrai-vos (oracao de sao bernardo de claraval a nossa senhora)': [
    { lang: 'Latim', text: 'Memorare, o piissima Virgo Maria, non esse auditum a saeculo quemquam ad tua currentem praesidia, tua implorantem auxilia, tua petentem suffragia esse derelictum. Ego tali animatus confidentia, ad te, Virgo Virginum, Mater, curro; ad te venio; coram te gemens peccator assisto. Noli, Mater Verbi, verba mea despicere, sed audi propitia et exaudi. Amen.' },
    { lang: 'Inglês', text: 'Remember, O most gracious Virgin Mary, that never was it known that anyone who fled to thy protection, implored thy help, or sought thy intercession was left unaided. Inspired by this confidence, I fly unto thee, O Virgin of virgins, my Mother. To thee do I come; before thee I stand, sinful and sorrowful. O Mother of the Word Incarnate, despise not my petitions, but in thy mercy hear and answer me. Amen.' },
  ],
  'oracao a sao miguel arcanjo': [
    { lang: 'Latim', text: 'Sancte Michael Archangele, defende nos in proelio; contra nequitiam et insidias diaboli esto praesidium. Imperet illi Deus, supplices deprecamur; tuque, Princeps militiae caelestis, Satanam aliosque spiritus malignos, qui ad perditionem animarum pervagantur in mundo, divina virtute in infernum detrude. Amen.' },
    { lang: 'Inglês', text: 'Saint Michael the Archangel, defend us in battle. Be our protection against the wickedness and snares of the devil. May God rebuke him, we humbly pray; and do thou, O Prince of the heavenly host, by the power of God, cast into hell Satan and all the evil spirits who prowl about the world seeking the ruin of souls. Amen.' },
  ],
}

function extraVersionsFor(title: string): PrayerVersion[] {
  const text = normalizeText(title)
  const exact = EXTRA_TRADITIONAL_VERSIONS[text]
  if (exact) return exact

  if (text === 'oracao do angelus' || text === 'angelus') {
    return [
      { lang: 'Latim', text: 'Angelus Domini nuntiavit Mariae. Et concepit de Spiritu Sancto.\nAve Maria, gratia plena, Dominus tecum; benedicta tu in mulieribus, et benedictus fructus ventris tui, Iesus. Sancta Maria, Mater Dei, ora pro nobis peccatoribus, nunc et in hora mortis nostrae. Amen.\n\nEcce ancilla Domini. Fiat mihi secundum verbum tuum.\nAve Maria, gratia plena, Dominus tecum; benedicta tu in mulieribus, et benedictus fructus ventris tui, Iesus. Sancta Maria, Mater Dei, ora pro nobis peccatoribus, nunc et in hora mortis nostrae. Amen.\n\nEt Verbum caro factum est. Et habitavit in nobis.\nAve Maria, gratia plena, Dominus tecum; benedicta tu in mulieribus, et benedictus fructus ventris tui, Iesus. Sancta Maria, Mater Dei, ora pro nobis peccatoribus, nunc et in hora mortis nostrae. Amen.\n\nOra pro nobis, sancta Dei Genetrix. Ut digni efficiamur promissionibus Christi.\n\nOremus: Gratiam tuam, quaesumus, Domine, mentibus nostris infunde; ut qui, Angelo nuntiante, Christi Filii tui incarnationem cognovimus, per passionem eius et crucem ad resurrectionis gloriam perducamur. Per eumdem Christum Dominum nostrum. Amen.' },
      { lang: 'Inglês', text: 'The Angel of the Lord declared unto Mary. And she conceived of the Holy Spirit.\nHail Mary, full of grace, the Lord is with thee. Blessed art thou among women, and blessed is the fruit of thy womb, Jesus. Holy Mary, Mother of God, pray for us sinners, now and at the hour of our death. Amen.\n\nBehold the handmaid of the Lord. Be it done unto me according to thy word.\nHail Mary, full of grace, the Lord is with thee. Blessed art thou among women, and blessed is the fruit of thy womb, Jesus. Holy Mary, Mother of God, pray for us sinners, now and at the hour of our death. Amen.\n\nAnd the Word was made flesh. And dwelt among us.\nHail Mary, full of grace, the Lord is with thee. Blessed art thou among women, and blessed is the fruit of thy womb, Jesus. Holy Mary, Mother of God, pray for us sinners, now and at the hour of our death. Amen.\n\nPray for us, O holy Mother of God. That we may be made worthy of the promises of Christ.\n\nLet us pray: Pour forth, we beseech thee, O Lord, thy grace into our hearts, that we, to whom the Incarnation of Christ thy Son was made known by the message of an angel, may by his Passion and Cross be brought to the glory of his Resurrection. Through the same Christ our Lord. Amen.' },
    ]
  }

  if (text === 'creio' || text === 'oracao do creio') {
    return [
      { lang: 'Latim', text: 'Credo in Deum Patrem omnipotentem, Creatorem caeli et terrae; et in Iesum Christum, Filium eius unicum, Dominum nostrum, qui conceptus est de Spiritu Sancto, natus ex Maria Virgine, passus sub Pontio Pilato, crucifixus, mortuus, et sepultus; descendit ad inferos; tertia die resurrexit a mortuis; ascendit ad caelos; sedet ad dexteram Dei Patris omnipotentis; inde venturus est iudicare vivos et mortuos. Credo in Spiritum Sanctum, sanctam Ecclesiam catholicam, sanctorum communionem, remissionem peccatorum, carnis resurrectionem, vitam aeternam. Amen.' },
      { lang: 'Inglês', text: 'I believe in God, the Father almighty, Creator of heaven and earth, and in Jesus Christ, his only Son, our Lord, who was conceived by the Holy Spirit, born of the Virgin Mary, suffered under Pontius Pilate, was crucified, died and was buried; he descended into hell; on the third day he rose again from the dead; he ascended into heaven, and is seated at the right hand of God the Father almighty; from there he will come to judge the living and the dead. I believe in the Holy Spirit, the holy Catholic Church, the communion of saints, the forgiveness of sins, the resurrection of the body, and life everlasting. Amen.' },
    ]
  }

  if (text.includes('ato de contricao')) {
    return EXTRA_TRADITIONAL_VERSIONS['ato de contricao']
  }

  if (text.includes('lembrai-vos')) {
    return EXTRA_TRADITIONAL_VERSIONS['lembrai-vos (oracao de sao bernardo de claraval a nossa senhora)']
  }

  if (text === 'o credo niceno-constantinopolitano') {
    return [
      { lang: 'Latim', text: 'Credo in unum Deum, Patrem omnipotentem, factorem caeli et terrae, visibilium omnium et invisibilium. Et in unum Dominum Iesum Christum, Filium Dei unigenitum, et ex Patre natum ante omnia saecula. Deum de Deo, lumen de lumine, Deum verum de Deo vero, genitum, non factum, consubstantialem Patri; per quem omnia facta sunt. Qui propter nos homines et propter nostram salutem descendit de caelis. Et incarnatus est de Spiritu Sancto ex Maria Virgine, et homo factus est. Crucifixus etiam pro nobis sub Pontio Pilato; passus et sepultus est, et resurrexit tertia die, secundum Scripturas, et ascendit in caelum, sedet ad dexteram Patris. Et iterum venturus est cum gloria, iudicare vivos et mortuos, cuius regni non erit finis. Et in Spiritum Sanctum, Dominum et vivificantem: qui ex Patre Filioque procedit. Qui cum Patre et Filio simul adoratur et conglorificatur: qui locutus est per prophetas. Et unam, sanctam, catholicam et apostolicam Ecclesiam. Confiteor unum baptisma in remissionem peccatorum. Et expecto resurrectionem mortuorum, et vitam venturi saeculi. Amen.' },
      { lang: 'Inglês', text: 'I believe in one God, the Father almighty, maker of heaven and earth, and of all things visible and invisible. And in one Lord Jesus Christ, the only begotten Son of God, born of the Father before all ages. God of God, Light of Light, true God of true God, begotten, not made, consubstantial with the Father; by whom all things were made. Who for us men and for our salvation came down from heaven, and was incarnate by the Holy Spirit of the Virgin Mary, and was made man. He was crucified also for us under Pontius Pilate; he suffered and was buried, and the third day he rose again according to the Scriptures. He ascended into heaven and sits at the right hand of the Father. He shall come again with glory to judge the living and the dead, and of his kingdom there shall be no end. And I believe in the Holy Spirit, the Lord and giver of life, who proceeds from the Father and the Son; who together with the Father and the Son is adored and glorified; who spoke by the prophets. And I believe in one, holy, catholic and apostolic Church. I confess one baptism for the remission of sins, and I look for the resurrection of the dead and the life of the world to come. Amen.' },
    ]
  }

  if (text.includes('sao miguel arcanjo')) {
    return [
      { lang: 'Latim', text: 'Sancte Michael Archangele, defende nos in proelio; contra nequitiam et insidias diaboli esto praesidium. Imperet illi Deus, supplices deprecamur; tuque, Princeps militiae caelestis, Satanam aliosque spiritus malignos, qui ad perditionem animarum pervagantur in mundo, divina virtute in infernum detrude. Amen.' },
      { lang: 'Inglês', text: 'Saint Michael the Archangel, defend us in battle. Be our protection against the wickedness and snares of the devil. May God rebuke him, we humbly pray; and do thou, O Prince of the heavenly host, by the power of God, cast into hell Satan and all the evil spirits who prowl about the world seeking the ruin of souls. Amen.' },
    ]
  }

  if (text === 'o magnificat') {
    return [
      { lang: 'Latim', text: 'Magnificat anima mea Dominum, et exsultavit spiritus meus in Deo salutari meo, quia respexit humilitatem ancillae suae. Ecce enim ex hoc beatam me dicent omnes generationes, quia fecit mihi magna qui potens est, et sanctum nomen eius. Et misericordia eius a progenie in progenies timentibus eum. Fecit potentiam in brachio suo, dispersit superbos mente cordis sui. Deposuit potentes de sede et exaltavit humiles. Esurientes implevit bonis et divites dimisit inanes. Suscepit Israel puerum suum, recordatus misericordiae suae, sicut locutus est ad patres nostros, Abraham et semini eius in saecula. Gloria Patri, et Filio, et Spiritui Sancto. Sicut erat in principio, et nunc, et semper, et in saecula saeculorum. Amen.' },
      { lang: 'Inglês', text: 'My soul doth magnify the Lord, and my spirit hath rejoiced in God my Savior, because he hath regarded the humility of his handmaid. For behold, from henceforth all generations shall call me blessed, because he that is mighty hath done great things to me, and holy is his name. And his mercy is from generation unto generations to them that fear him. He hath showed might in his arm; he hath scattered the proud in the conceit of their heart. He hath put down the mighty from their seat and hath exalted the humble. He hath filled the hungry with good things, and the rich he hath sent empty away. He hath received Israel his servant, being mindful of his mercy, as he spoke to our fathers, to Abraham and to his seed forever. Glory be to the Father, and to the Son, and to the Holy Spirit. As it was in the beginning, is now, and ever shall be, world without end. Amen.' },
    ]
  }

  if (text.includes('almas do purgatorio') || text.includes('falecidos')) {
    return [
      { lang: 'Latim', text: 'Requiem aeternam dona eis, Domine, et lux perpetua luceat eis. Requiescant in pace. Amen.' },
      { lang: 'Inglês', text: 'Eternal rest grant unto them, O Lord, and let perpetual light shine upon them. May they rest in peace. Amen.' },
    ]
  }

  if (text === 'oracao ao espirito santo' || text.includes('vem, espirito santo')) {
    return [
      { lang: 'Latim', text: 'Veni, Sancte Spiritus, reple tuorum corda fidelium, et tui amoris in eis ignem accende. Emitte Spiritum tuum et creabuntur. Et renovabis faciem terrae.' },
      { lang: 'Inglês', text: 'Come, Holy Spirit, fill the hearts of thy faithful and kindle in them the fire of thy love. Send forth thy Spirit and they shall be created. And thou shalt renew the face of the earth.' },
    ]
  }

  if (text.includes('sao bento') || text.includes('medalha de sao bento')) {
    return [
      { lang: 'Latim', text: 'Crux sacra sit mihi lux. Non draco sit mihi dux. Vade retro Satana. Numquam suade mihi vana. Sunt mala quae libas. Ipse venena bibas. In nomine Patris, et Filii, et Spiritus Sancti. Amen.' },
      { lang: 'Inglês', text: 'May the holy Cross be my light. May the dragon never be my guide. Begone, Satan. Never tempt me with thy vanities. What thou offerest me is evil. Drink thou thine own poison. In the name of the Father, and of the Son, and of the Holy Spirit. Amen.' },
    ]
  }

  if (text === 'oracao a cruz' || text.includes('forca da cruz')) {
    return [
      { lang: 'Latim', text: 'Adoramus te, Christe, et benedicimus tibi, quia per sanctam crucem tuam redemisti mundum. Amen.' },
      { lang: 'Inglês', text: 'We adore thee, O Christ, and we bless thee, because by thy holy Cross thou hast redeemed the world. Amen.' },
    ]
  }

  if (text.includes('veni creator') || text.includes('espirito criador')) {
    return [
      { lang: 'Latim', text: 'Veni, Creator Spiritus, mentes tuorum visita, imple superna gratia quae tu creasti pectora. Qui diceris Paraclitus, altissimi donum Dei, fons vivus, ignis, caritas, et spiritalis unctio. Tu septiformis munere, digitus paternae dexterae, tu rite promissum Patris, sermone ditans guttura. Accende lumen sensibus, infunde amorem cordibus, infirma nostri corporis virtute firmans perpeti. Hostem repellas longius pacemque dones protinus; ductore sic te praevio vitemus omne noxium. Per te sciamus da Patrem noscamus atque Filium, te utriusque Spiritum credamus omni tempore. Deo Patri sit gloria, et Filio, qui a mortuis surrexit, ac Paraclito, in saeculorum saecula. Amen.' },
      { lang: 'Inglês', text: 'Come, Holy Ghost, Creator blest, and in our hearts take up thy rest; come with thy grace and heavenly aid to fill the hearts which thou hast made. To thee, the Comforter, we cry; to thee, the gift of God Most High; the fount of life, the fire of love, the soul\'s anointing from above. Drive far away our wily foe, and thine abiding peace bestow; if thou be our protecting guide, no evil can our steps betide. Praise we the Father and the Son and Holy Spirit with them one; and may the Son on us bestow the gifts that from the Spirit flow. Amen.' },
    ]
  }

  if (text.includes('sequencia de pentecostes') || text.includes('sequencia da missa de pentecostes')) {
    return [
      { lang: 'Latim', text: 'Veni, Sancte Spiritus, et emitte caelitus lucis tuae radium. Veni, pater pauperum; veni, dator munerum; veni, lumen cordium. Consolator optime, dulcis hospes animae, dulce refrigerium. In labore requies, in aestu temperies, in fletu solacium. O lux beatissima, reple cordis intima tuorum fidelium. Sine tuo numine nihil est in homine, nihil est innoxium. Lava quod est sordidum, riga quod est aridum, sana quod est saucium. Flecte quod est rigidum, fove quod est frigidum, rege quod est devium. Da tuis fidelibus, in te confidentibus, sacrum septenarium. Da virtutis meritum, da salutis exitum, da perenne gaudium. Amen. Alleluia.' },
      { lang: 'Inglês', text: 'Come, Holy Spirit, come; and from thy celestial home shed a ray of light divine. Come, Father of the poor; come, source of all our store; come, within our bosoms shine. Thou, of comforters the best; thou, the soul\'s most welcome guest; sweet refreshment here below. In our labor, rest most sweet; grateful coolness in the heat; solace in the midst of woe. O most blessed Light divine, shine within these hearts of thine, and our inmost being fill. Where thou art not, man hath naught, nothing good in deed or thought, nothing free from taint of ill. Heal our wounds, our strength renew; on our dryness pour thy dew; wash the stains of guilt away. Bend the stubborn heart and will; melt the frozen, warm the chill; guide the steps that go astray. On thy faithful, who adore and confess thee evermore, in thy sevenfold gift descend. Give them virtue\'s sure reward; give them thy salvation, Lord; give them joys that never end. Amen. Alleluia.' },
    ]
  }

  if (text.includes('sequencia da pascoa')) {
    return [
      { lang: 'Latim', text: 'Victimae paschali laudes immolent Christiani. Agnus redemit oves: Christus innocens Patri reconciliavit peccatores. Mors et vita duello conflixere mirando: dux vitae mortuus regnat vivus. Dic nobis Maria, quid vidisti in via? Sepulcrum Christi viventis et gloriam vidi resurgentis. Angelicos testes, sudarium et vestes. Surrexit Christus spes mea: praecedet suos in Galilaeam. Scimus Christum surrexisse a mortuis vere: tu nobis, victor Rex, miserere. Amen. Alleluia.' },
      { lang: 'Inglês', text: 'Christians, to the Paschal Victim offer your thankful praises. A Lamb the sheep redeemeth: Christ, who only is sinless, reconcileth sinners to the Father. Death and life have contended in that combat stupendous: the Prince of life, who died, reigns immortal. Speak, Mary, declaring what thou sawest wayfaring. The tomb of Christ, who is living, the glory of Jesus rising. Bright angels attesting, the shroud and napkin resting. Yea, Christ my hope is arisen; to Galilee he goes before you. Christ indeed from death is risen, our new life obtaining. Have mercy, victor King, ever reigning. Amen. Alleluia.' },
    ]
  }

  if (text === 'te deum') {
    return [
      { lang: 'Latim', text: 'Te Deum laudamus: te Dominum confitemur. Te aeternum Patrem omnis terra veneratur. Tibi omnes Angeli, tibi caeli et universae potestates, tibi Cherubim et Seraphim incessabili voce proclamant: Sanctus, Sanctus, Sanctus Dominus Deus Sabaoth. Pleni sunt caeli et terra maiestatis gloriae tuae. Te gloriosus Apostolorum chorus, te Prophetarum laudabilis numerus, te Martyrum candidatus laudat exercitus. Te per orbem terrarum sancta confitetur Ecclesia: Patrem immensae maiestatis; venerandum tuum verum et unicum Filium; Sanctum quoque Paraclitum Spiritum. Tu rex gloriae, Christe. Tu Patris sempiternus es Filius. Tu, ad liberandum suscepturus hominem, non horruisti Virginis uterum. Tu, devicto mortis aculeo, aperuisti credentibus regna caelorum. Tu ad dexteram Dei sedes in gloria Patris. Iudex crederis esse venturus. Te ergo quaesumus, tuis famulis subveni, quos pretioso sanguine redemisti. Aeterna fac cum sanctis tuis in gloria numerari. Salvum fac populum tuum, Domine, et benedic hereditati tuae. Et rege eos, et extolle illos usque in aeternum. Per singulos dies benedicimus te. Et laudamus nomen tuum in saeculum, et in saeculum saeculi. Dignare, Domine, die isto sine peccato nos custodire. Miserere nostri, Domine, miserere nostri. Fiat misericordia tua, Domine, super nos, quemadmodum speravimus in te. In te, Domine, speravi: non confundar in aeternum.' },
      { lang: 'Inglês', text: 'We praise thee, O God; we acknowledge thee to be the Lord. All the earth doth worship thee, the Father everlasting. To thee all angels cry aloud, the heavens and all the powers therein. To thee Cherubim and Seraphim continually do cry: Holy, Holy, Holy, Lord God of Sabaoth; heaven and earth are full of the majesty of thy glory. The glorious company of the apostles praise thee. The goodly fellowship of the prophets praise thee. The noble army of martyrs praise thee. The holy Church throughout all the world doth acknowledge thee: the Father of an infinite majesty; thine honorable, true and only Son; also the Holy Ghost, the Comforter. Thou art the King of glory, O Christ. Thou art the everlasting Son of the Father. When thou tookest upon thee to deliver man, thou didst not abhor the Virgin\'s womb. When thou hadst overcome the sharpness of death, thou didst open the kingdom of heaven to all believers. Thou sittest at the right hand of God in the glory of the Father. We believe that thou shalt come to be our judge. We therefore pray thee, help thy servants whom thou hast redeemed with thy precious blood. Make them to be numbered with thy saints in glory everlasting. O Lord, save thy people and bless thine heritage. Govern them and lift them up forever. Day by day we magnify thee, and we worship thy name ever world without end. Vouchsafe, O Lord, to keep us this day without sin. O Lord, have mercy upon us, have mercy upon us. O Lord, let thy mercy lighten upon us, as our trust is in thee. O Lord, in thee have I trusted; let me never be confounded.' },
    ]
  }

  return []
}

function isCompleteExtraVersion(version: PrayerVersion): boolean {
  return version.text.trim().length > 0 && !version.text.includes('...')
}

function mergeVersions(versions: PrayerVersion[]): PrayerVersion[] {
  const byLanguage = new Map<PrayerVersion['lang'], PrayerVersion>()
  versions
    .filter(isCompleteExtraVersion)
    .forEach(version => byLanguage.set(version.lang, version))

  return (['Português', 'Latim', 'Inglês'] as PrayerVersion['lang'][])
    .map(lang => byLanguage.get(lang))
    .filter((version): version is PrayerVersion => Boolean(version))
}

function isExactBasicPrayer(title: string): boolean {
  return [
    'ave-maria',
    'ave maria',
    'creio',
    'gloria ao pai',
    'o credo niceno-constantinopolitano',
    'oracao do creio',
    'pai-nosso',
    'pai nosso',
    'persignacao',
    'santo anjo do senhor',
  ].includes(title)
}

function categorizePrayer(title: string): GroupCode {
  const text = normalizeText(title)

  if (includesAny(text, ['novena', 'triduo', 'decenario', 'trintena'])) return 'NOV'
  if (includesAny(text, ['via-sacra', 'via sacra', 'sete palavras', 'cruz', 'sagrada face'])) return 'VIACR'
  if (includesAny(text, ['sequencia', 'te deum', 'gloria a deus nas alturas', 'ritos iniciais'])) return 'SEQ'
  if (includesAny(text, [
    'eucarist',
    'sacramentado',
    'santissimo',
    'alma de cristo',
    'comunhao',
    'missa',
    'acolito',
    'corpus christi',
    'preciosissimo sangue',
    'sangue de jesus',
    'santas chagas',
    'chagas',
  ])) return 'EUCA'
  if (includesAny(text, ['espirito santo', 'pentecostes', 'veni creator', 'vem, espirito', 'sabedoria de salomao', 'divino espirito'])) return 'ESP'
  if (includesAny(text, [
    'santo agostinho',
    'santo afonso',
    'santo alberto',
    'santo ambrosio',
    'santo anselmo',
    'santo atanasio',
    'santo efram',
    'santo efrem',
    'santo hilario',
    'santo irineu',
    'sao basilio',
    'sao bernardo',
    'sao boaventura',
    'sao cirilo',
    'sao gregorio',
    'sao jeronimo',
    'sao joao crisostomo',
    'sao joao da cruz',
    'sao joao damasceno',
    'sao joao de avila',
    'sao leao magno',
    'sao lourenco de brindisi',
    'sao pedro crisologo',
    'sao pedro damiao',
    'sao roberto belarmino',
    'sao tomas de aquino',
    'santa catarina de sena',
    'santa hildegarda',
    'santa teresa de avila',
    'tarde te amei',
    'gregorio de narek',
  ])) return 'DOUT'
  if (includesAny(text, ['biblia', 'evangelho', 'padre jonas', 'palavra de deus', 'prologo do evangelho'])) return 'BIBLIA'
  if (includesAny(text, ['oracao da manha', 'oracao da noite', 'oferecimento do dia', 'exame de consciencia', 'ato de contricao', 'confissao'])) return 'DIARIA'
  if (isExactBasicPrayer(text)) return 'BASE'
  if (includesAny(text, ['sao jose', 'são jose', 'pai adotivo de jesus', 'jose dormindo', 'coracao de sao jose'])) return 'JOSE'
  if (includesAny(text, [
    'nossa senhora',
    'maria,',
    'maria santissima',
    'mariano',
    'mariana',
    'rosario',
    'salve-rainha',
    'salve rainha',
    'angelus',
    'magnificat',
    'imaculada',
    'aparecida',
    'fatima',
    'lourdes',
    'carmo',
    'perpetuo socorro',
    'desatadora',
    'pieta',
    'virgem',
    'auxiliadora',
    'desterro',
    'guadalupe',
    'nazare',
  ])) return 'MARIA'
  if (includesAny(text, ['sao luigi maria'])) return 'SANTOS'
  if (includesAny(text, [
    'santa ',
    'santas ',
    'nha chica',
    'madre teresa',
    'teresinha',
    'rita',
    'clara',
    'gianna',
    'edwiges',
    'luzia',
    'margarida',
    'paulina',
    'dulce',
  ])) return 'SANTAS'
  if (includesAny(text, ['sao ', 'santo ', 'santos ', 'arcanjo', 'anjo da guarda', 'anjos', 'beato', 'padre pio', 'carlo acutis', 'pier giorgio'])) return 'SANTOS'

  return 'DIV'
}

function decodeHtmlEntities(value: string): string {
  const namedEntities: Record<string, string> = {
    amp: '&',
    apos: "'",
    bull: '•',
    copy: '©',
    hellip: '...',
    nbsp: ' ',
    ndash: '-',
    mdash: '-',
    quot: '"',
    rsquo: "'",
    lsquo: "'",
    rdquo: '"',
    ldquo: '"',
    shy: '',
    gt: '>',
    lt: '<',
  }

  return value.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (entity, code) => {
    if (code.startsWith('#x')) {
      return String.fromCodePoint(Number.parseInt(code.slice(2), 16))
    }
    if (code.startsWith('#')) {
      return String.fromCodePoint(Number.parseInt(code.slice(1), 10))
    }
    return namedEntities[code] ?? entity
  })
}

function stripPrayerHtml(html: string): string {
  const text = html
    .replace(/<!doctype[^>]*>/gi, ' ')
    .replace(/<head[\s\S]*?<\/head>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|h[1-6]|li|blockquote)>/gi, '\n\n')
    .replace(/<li[^>]*>/gi, '- ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\r/g, '')

  return decodeHtmlEntities(text)
    .split('\n')
    .map(line => line.replace(/[ \t]+/g, ' ').trim())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function formatModifiedDate(value?: string): string | undefined {
  if (!value) return undefined
  const [date] = value.split(' ')
  return date || value
}

function createEmptyGroups(): Record<GroupCode, PrayerGroup> {
  return GROUP_META.reduce((groups, meta) => {
    groups[meta.code] = {
      title: meta.title,
      description: meta.description,
      code: meta.code,
      items: [],
    }
    return groups
  }, {} as Record<GroupCode, PrayerGroup>)
}

function buildPrayerGroups(remotePrayers: RemotePrayer[]): PrayerGroup[] {
  const groups = createEmptyGroups()

  remotePrayers.forEach((remotePrayer, index) => {
    const title = remotePrayer.titulo?.trim() || `Oração ${index + 1}`
    const text = stripPrayerHtml(remotePrayer.texto ?? '')
    const code = categorizePrayer(title)

    const versions = mergeVersions([
      {
        lang: 'Português',
        text: text || title,
      },
      ...extraVersionsFor(title),
    ])

    groups[code].items.push({
      id: String(remotePrayer.id ?? remotePrayer.dia ?? `${code}-${index}`),
      title,
      modified: formatModifiedDate(remotePrayer.modified),
      source: 'Canção Nova - Liturgia Diária',
      versions,
    })
  })

  return GROUP_META
    .map(meta => ({
      ...groups[meta.code],
      items: groups[meta.code].items.sort((a, b) => a.title.localeCompare(b.title, 'pt-BR')),
    }))
    .filter(group => group.items.length > 0)
}

async function getPrayerGroups(): Promise<{
  groups: PrayerGroup[]
  source: string
  sourceUrl?: string
  latestModified?: string
  isFallback: boolean
}> {
  try {
    const response = await fetch(CANCAO_NOVA_PRAYERS_URL, {
      next: { revalidate },
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const data = (await response.json()) as RemotePrayerResponse
    const prayers = Array.isArray(data.oracoes) ? data.oracoes : []
    if (prayers.length === 0) throw new Error('Nenhuma oração retornada')

    const latestModified = prayers
      .map(prayer => prayer.modified)
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1)

    return {
      groups: buildPrayerGroups(prayers),
      source: 'Acervo de orações do app Liturgia Diária - Canção Nova',
      sourceUrl: CANCAO_NOVA_PRAYERS_URL,
      latestModified: formatModifiedDate(latestModified),
      isFallback: false,
    }
  } catch {
    return {
      groups: fallbackPrayerGroups,
      source: 'Fallback local Vera.Fidei',
      isFallback: true,
    }
  }
}

export default async function OracoesPage() {
  const { groups, source, sourceUrl, latestModified, isFallback } = await getPrayerGroups()

  return (
    <div className="mx-auto max-w-3xl px-4 pt-8 pb-4">
      <BrandHeader
        title="Orações"
        description="Roteiros de oração, devoções tradicionais e espiritualidade ligada às fontes da Biblioteca."
      />
      <OracoesView
        groups={groups}
        source={source}
        sourceUrl={sourceUrl}
        latestModified={latestModified}
        isFallback={isFallback}
      />
    </div>
  )
}
