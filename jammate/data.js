/* JamMate — dati di esempio (seed) e costanti.
 * In un'app reale arriverebbero da un server/database.
 * Qui servono a mostrare una città "piena" così il prototipo non è un deserto. */

const INSTRUMENTS = [
  "Voce", "Chitarra", "Chitarra elettrica", "Basso", "Batteria",
  "Pianoforte", "Tastiere", "Violino", "Sax", "Tromba", "DJ / Producer"
];

const LEVELS = ["Principiante", "Intermedio", "Avanzato", "Professionista"];

const GENRES = [
  "Rock", "Pop", "Jazz", "Blues", "Metal", "Funk", "Indie",
  "Cantautorato", "Reggae", "Elettronica", "Classica", "Folk", "Soul"
];

const KEYS = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si",
              "Dom", "Do#m", "Rem", "Mibm", "Mim", "Fam", "Solm", "Lam", "Sibm", "Sim"];

const GRADS = [
  "linear-gradient(135deg,#7c5cff,#ff5c8a)",
  "linear-gradient(135deg,#36d1dc,#5b86e5)",
  "linear-gradient(135deg,#f7971e,#ffd200)",
  "linear-gradient(135deg,#11998e,#38ef7d)",
  "linear-gradient(135deg,#fc466b,#3f5efb)",
  "linear-gradient(135deg,#ee0979,#ff6a00)",
  "linear-gradient(135deg,#8e2de2,#4a00e0)",
  "linear-gradient(135deg,#00b4db,#0083b0)"
];

const SEED_PROFILES = [
  {
    id: "u1", name: "Marco Bassani", avatar: "🎸", color: GRADS[0], city: "Milano", distanceKm: 2,
    tagline: "Riff, groove e amplificatori a palla.",
    instruments: ["Chitarra elettrica", "Voce"], level: "Avanzato",
    genres: ["Rock", "Blues", "Funk"],
    bio: "Chitarrista da 12 anni, cerco una band rock/blues con cui suonare dal vivo. Ho una sala prove in zona Lambrate.",
    links: { youtube: "https://youtube.com", spotify: "https://spotify.com", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Sultans of Swing", artist: "Dire Straits", key: "Rem" },
      { title: "Hotel California", artist: "Eagles", key: "Sim" },
      { title: "Sweet Child o' Mine", artist: "Guns N' Roses", key: "Re" }
    ],
    endo: { puntualita: 95, tecnica: 88, attitudine: 92 }
  },
  {
    id: "u2", name: "Giulia Ferri", avatar: "🎤", color: GRADS[4], city: "Milano", distanceKm: 5,
    tagline: "La voce che cercavi per la tua cover band.",
    instruments: ["Voce"], level: "Professionista",
    genres: ["Pop", "Soul", "Jazz"],
    bio: "Cantante professionista, esperienza in cover band per eventi. Cerco musicisti affidabili per un progetto soul/pop.",
    links: { youtube: "https://youtube.com", spotify: "", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Valerie", artist: "Amy Winehouse", key: "Mi" },
      { title: "Rolling in the Deep", artist: "Adele", key: "Dom" },
      { title: "Hotel California", artist: "Eagles", key: "Sim" }
    ],
    endo: { puntualita: 90, tecnica: 96, attitudine: 89 }
  },
  {
    id: "u3", name: "Davide Conti", avatar: "🥁", color: GRADS[3], city: "Milano", distanceKm: 8,
    tagline: "Tengo il tempo, non i rancori.",
    instruments: ["Batteria"], level: "Intermedio",
    genres: ["Rock", "Indie", "Metal"],
    bio: "Batterista, disponibile sere e weekend. Cerco gente seria ma per divertirsi, non per litigare sui pezzi.",
    links: { youtube: "", spotify: "", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Seven Nation Army", artist: "The White Stripes", key: "Mi" },
      { title: "Mr. Brightside", artist: "The Killers", key: "Re" }
    ],
    endo: { puntualita: 82, tecnica: 80, attitudine: 94 }
  },
  {
    id: "u4", name: "Sara Lombardi", avatar: "🎹", color: GRADS[1], city: "Monza", distanceKm: 16,
    tagline: "Jazz nel cuore, aperta a tutto.",
    instruments: ["Pianoforte", "Tastiere", "Voce"], level: "Avanzato",
    genres: ["Jazz", "Pop", "Cantautorato"],
    bio: "Pianista e tastierista, amo il jazz ma me la cavo su tutto. Aperta a jam session e progetti originali.",
    links: { youtube: "https://youtube.com", spotify: "https://spotify.com", instagram: "" },
    repertoire: [
      { title: "Autumn Leaves", artist: "Standard jazz", key: "Solm" },
      { title: "Someone Like You", artist: "Adele", key: "La" },
      { title: "Valerie", artist: "Amy Winehouse", key: "Mi" }
    ],
    endo: { puntualita: 97, tecnica: 91, attitudine: 88 }
  },
  {
    id: "u5", name: "Luca Greco", avatar: "🎸", color: GRADS[6], city: "Milano", distanceKm: 3,
    tagline: "Slap a richiesta 😎",
    instruments: ["Basso"], level: "Avanzato",
    genres: ["Funk", "Jazz", "Rock"],
    bio: "Bassista groove-oriented. Cerco una band funk/soul.",
    links: { youtube: "", spotify: "https://spotify.com", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Superstition", artist: "Stevie Wonder", key: "Re#" },
      { title: "Get Lucky", artist: "Daft Punk", key: "Sim" }
    ],
    endo: { puntualita: 88, tecnica: 93, attitudine: 90 }
  },
  {
    id: "u6", name: "Elena Marchi", avatar: "🎻", color: GRADS[2], city: "Milano", distanceKm: 11,
    tagline: "Archi classici con anima pop.",
    instruments: ["Violino"], level: "Professionista",
    genres: ["Classica", "Folk", "Pop"],
    bio: "Violinista di formazione classica, mi piace contaminare con pop e folk. Disponibile per archi e registrazioni.",
    links: { youtube: "https://youtube.com", spotify: "", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Viva la Vida", artist: "Coldplay", key: "Lab" },
      { title: "Someone Like You", artist: "Adele", key: "La" }
    ],
    endo: { puntualita: 99, tecnica: 95, attitudine: 85 }
  },
  {
    id: "u7", name: "Tommaso Riva", avatar: "🎷", color: GRADS[5], city: "Milano", distanceKm: 6,
    tagline: "Sax tenore in cerca di groove.",
    instruments: ["Sax"], level: "Intermedio",
    genres: ["Jazz", "Funk", "Blues"],
    bio: "Sax tenore. Cerco una jam session settimanale per fare pratica e conoscere gente.",
    links: { youtube: "", spotify: "", instagram: "" },
    repertoire: [
      { title: "Take Five", artist: "Dave Brubeck", key: "Mibm" },
      { title: "Superstition", artist: "Stevie Wonder", key: "Re#" }
    ],
    endo: { puntualita: 78, tecnica: 84, attitudine: 91 }
  },
  {
    id: "u8", name: "Chiara Vitale", avatar: "🎤", color: GRADS[7], city: "Sesto S.G.", distanceKm: 13,
    tagline: "Scrivo canzoni mie, cerco la mia band.",
    instruments: ["Voce", "Chitarra"], level: "Intermedio",
    genres: ["Indie", "Cantautorato", "Pop"],
    bio: "Scrivo canzoni mie, cerco chi mi aiuti ad arrangiarle. Influenze: Cremonini, Coldplay, The 1975.",
    links: { youtube: "https://youtube.com", spotify: "https://spotify.com", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Yellow", artist: "Coldplay", key: "Si" },
      { title: "Mr. Brightside", artist: "The Killers", key: "Re" }
    ],
    endo: { puntualita: 86, tecnica: 79, attitudine: 96 }
  },
  {
    id: "u9", name: "Andrea Russo", avatar: "🎸", color: GRADS[6], city: "Milano", distanceKm: 4,
    tagline: "Metal nel sangue, doppia cassa ovunque.",
    instruments: ["Chitarra elettrica"], level: "Avanzato",
    genres: ["Metal", "Rock"],
    bio: "Chitarrista metal, cerco batterista veloce e bassista per progetto thrash. No perditempo.",
    links: { youtube: "https://youtube.com", spotify: "", instagram: "" },
    repertoire: [
      { title: "Master of Puppets", artist: "Metallica", key: "Mi" },
      { title: "Painkiller", artist: "Judas Priest", key: "Mi" }
    ],
    endo: { puntualita: 84, tecnica: 92, attitudine: 76 }
  },
  {
    id: "u10", name: "Francesca Neri", avatar: "🎹", color: GRADS[1], city: "Milano", distanceKm: 9,
    tagline: "Synth, pad e atmosfere.",
    instruments: ["Tastiere", "DJ / Producer"], level: "Intermedio",
    genres: ["Elettronica", "Pop", "Indie"],
    bio: "Producer e tastierista, lavoro in studio e dal vivo. Cerco una voce per un progetto synth-pop.",
    links: { youtube: "", spotify: "https://spotify.com", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Get Lucky", artist: "Daft Punk", key: "Sim" },
      { title: "Yellow", artist: "Coldplay", key: "Si" }
    ],
    endo: { puntualita: 91, tecnica: 87, attitudine: 93 }
  },
  {
    id: "u11", name: "Paolo De Santis", avatar: "🎺", color: GRADS[2], city: "Milano", distanceKm: 7,
    tagline: "Fiati e sezione ritmica? Presente.",
    instruments: ["Tromba"], level: "Professionista",
    genres: ["Jazz", "Funk", "Soul"],
    bio: "Trombettista con esperienza in big band. Disponibile per sezioni fiati e arrangiamenti.",
    links: { youtube: "https://youtube.com", spotify: "", instagram: "" },
    repertoire: [
      { title: "Superstition", artist: "Stevie Wonder", key: "Re#" },
      { title: "Take Five", artist: "Dave Brubeck", key: "Mibm" }
    ],
    endo: { puntualita: 96, tecnica: 94, attitudine: 90 }
  },
  {
    id: "u12", name: "Martina Bruno", avatar: "🥁", color: GRADS[4], city: "Cinisello", distanceKm: 14,
    tagline: "Groove pulito, sorriso garantito.",
    instruments: ["Batteria", "Voce"], level: "Avanzato",
    genres: ["Pop", "Funk", "Soul"],
    bio: "Batterista e corista. Amo i groove puliti e le band organizzate. Cerco progetto pop/soul attivo.",
    links: { youtube: "", spotify: "https://spotify.com", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Rolling in the Deep", artist: "Adele", key: "Dom" },
      { title: "Get Lucky", artist: "Daft Punk", key: "Sim" }
    ],
    endo: { puntualita: 93, tecnica: 89, attitudine: 95 }
  }
];

const SEED_EVENTS = [
  {
    id: "e1", title: "Cerchiamo bassista per cover band anni '80",
    author: "The Neon Lights", authorAvatar: "🎸", city: "Milano", distanceKm: 4,
    date: "2026-06-27", genres: ["Pop", "Rock"],
    description: "Cover band rodata, suoniamo in locali della zona. Ci manca solo il basso. Prove il martedì sera a Lambrate.",
    slots: [
      { instrument: "Basso", filled: false },
      { instrument: "Voce", filled: true },
      { instrument: "Chitarra elettrica", filled: true },
      { instrument: "Batteria", filled: true }
    ]
  },
  {
    id: "e2", title: "Jam session blues — aperta a tutti",
    author: "Officina del Blues", authorAvatar: "🎷", city: "Milano", distanceKm: 7,
    date: "2026-06-20", genres: ["Blues", "Funk"],
    description: "Jam libera ogni venerdì. Porta il tuo strumento, si suona in 12 battute. Birra offerta ai nuovi! 🍺",
    slots: [
      { instrument: "Chitarra elettrica", filled: false },
      { instrument: "Sax", filled: false },
      { instrument: "Pianoforte", filled: false }
    ]
  },
  {
    id: "e3", title: "Progetto originale indie cerca batterista",
    author: "Giulia & co.", authorAvatar: "🥁", city: "Monza", distanceKm: 15,
    date: "2026-07-04", genres: ["Indie", "Cantautorato"],
    description: "Abbiamo 5 brani originali pronti, vogliamo registrare un EP. Cerchiamo un batterista che sappia anche dare idee.",
    slots: [
      { instrument: "Batteria", filled: false },
      { instrument: "Voce", filled: true },
      { instrument: "Chitarra", filled: true },
      { instrument: "Basso", filled: true }
    ]
  }
];

const SEED_MESSAGES = {
  u2: [
    { from: "them", text: "Ciao! Ho visto che cerchi una band soul, io canto 🎤" },
    { from: "me", text: "Ciao Giulia! Sì esatto, che repertorio hai?" },
    { from: "them", text: "Amy Winehouse, Adele, un po' di Beyoncé. Tu su che pezzi te la cavi?" }
  ]
};
