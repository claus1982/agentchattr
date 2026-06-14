/* JamMate — dati di esempio (seed) e costanti.
 * In un'app reale questi dati arriverebbero da un server/database.
 * Qui servono a mostrare una città "piena" così il prototipo non è un deserto. */

const INSTRUMENTS = [
  "Voce", "Chitarra", "Chitarra elettrica", "Basso", "Batteria",
  "Pianoforte", "Tastiere", "Violino", "Sax", "Tromba", "DJ / Producer"
];

const LEVELS = ["Principiante", "Intermedio", "Avanzato", "Professionista"];

const GENRES = [
  "Rock", "Pop", "Jazz", "Blues", "Metal", "Funk", "Indie",
  "Cantautorato", "Reggae", "Elettronica", "Classica", "Folk"
];

const KEYS = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si",
              "Dom", "Rem", "Mim", "Fam", "Solm", "Lam", "Sim"];

const SEED_PROFILES = [
  {
    id: "u1", name: "Marco Bassani", avatar: "🎸", city: "Milano", distanceKm: 2,
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
    id: "u2", name: "Giulia Ferri", avatar: "🎤", city: "Milano", distanceKm: 5,
    instruments: ["Voce"], level: "Professionista",
    genres: ["Pop", "Soul", "Jazz"],
    bio: "Cantante professionista, esperienza in cover band per eventi. Cerco musicisti affidabili per un progetto soul/pop.",
    links: { youtube: "https://youtube.com", spotify: "", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Valerie", artist: "Amy Winehouse", key: "Mi" },
      { title: "Rolling in the Deep", artist: "Adele", key: "Dom" },
      { title: "Halo", artist: "Beyoncé", key: "La" }
    ],
    endo: { puntualita: 90, tecnica: 96, attitudine: 89 }
  },
  {
    id: "u3", name: "Davide Conti", avatar: "🥁", city: "Milano", distanceKm: 8,
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
    id: "u4", name: "Sara Lombardi", avatar: "🎹", city: "Monza", distanceKm: 16,
    instruments: ["Pianoforte", "Tastiere", "Voce"], level: "Avanzato",
    genres: ["Jazz", "Pop", "Cantautorato"],
    bio: "Pianista e tastierista, amo il jazz ma me la cavo su tutto. Aperta a jam session e progetti originali.",
    links: { youtube: "https://youtube.com", spotify: "https://spotify.com", instagram: "" },
    repertoire: [
      { title: "Autumn Leaves", artist: "Standard jazz", key: "Solm" },
      { title: "Someone Like You", artist: "Adele", key: "La" },
      { title: "La cura", artist: "Battiato", key: "Do" }
    ],
    endo: { puntualita: 97, tecnica: 91, attitudine: 88 }
  },
  {
    id: "u5", name: "Luca Greco", avatar: "🎸", city: "Milano", distanceKm: 3,
    instruments: ["Basso"], level: "Avanzato",
    genres: ["Funk", "Jazz", "Rock"],
    bio: "Bassista groove-oriented. Cerco una band funk/soul. Slap a richiesta 😎",
    links: { youtube: "", spotify: "https://spotify.com", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Superstition", artist: "Stevie Wonder", key: "Re#" },
      { title: "Get Lucky", artist: "Daft Punk", key: "Sim" }
    ],
    endo: { puntualita: 88, tecnica: 93, attitudine: 90 }
  },
  {
    id: "u6", name: "Elena Marchi", avatar: "🎻", city: "Milano", distanceKm: 11,
    instruments: ["Violino"], level: "Professionista",
    genres: ["Classica", "Folk", "Pop"],
    bio: "Violinista di formazione classica, mi piace contaminare con pop e folk. Disponibile per archi e registrazioni.",
    links: { youtube: "https://youtube.com", spotify: "", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Viva la Vida", artist: "Coldplay", key: "Lab" },
      { title: "Czardas", artist: "Monti", key: "Rem" }
    ],
    endo: { puntualita: 99, tecnica: 95, attitudine: 85 }
  },
  {
    id: "u7", name: "Tommaso Riva", avatar: "🎷", city: "Milano", distanceKm: 6,
    instruments: ["Sax"], level: "Intermedio",
    genres: ["Jazz", "Funk", "Blues"],
    bio: "Sax tenore. Cerco una jam session settimanale per fare pratica e conoscere gente.",
    links: { youtube: "", spotify: "", instagram: "" },
    repertoire: [
      { title: "Take Five", artist: "Dave Brubeck", key: "Mibm" },
      { title: "Careless Whisper", artist: "George Michael", key: "Rem" }
    ],
    endo: { puntualita: 78, tecnica: 84, attitudine: 91 }
  },
  {
    id: "u8", name: "Chiara Vitale", avatar: "🎤", city: "Sesto S.G.", distanceKm: 13,
    instruments: ["Voce", "Chitarra"], level: "Intermedio",
    genres: ["Indie", "Cantautorato", "Pop"],
    bio: "Scrivo canzoni mie, cerco chi mi aiuti ad arrangiarle. Influenze: Cremonini, Coldplay, The 1975.",
    links: { youtube: "https://youtube.com", spotify: "https://spotify.com", instagram: "https://instagram.com" },
    repertoire: [
      { title: "Yellow", artist: "Coldplay", key: "Si" },
      { title: "Poetica", artist: "Cesare Cremonini", key: "Do" }
    ],
    endo: { puntualita: 86, tecnica: 79, attitudine: 96 }
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
