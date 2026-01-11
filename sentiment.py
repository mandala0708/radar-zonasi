import re  # Library untuk manipulasi teks menggunakan regular expressions
from textblob import TextBlob  # Library untuk analisis sentimen berbasis bahasa Inggris
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # Library VADER untuk analisis sentimen

sia = SentimentIntensityAnalyzer()  # Inisialisasi analyzer VADER

# ------------------- VADER Indonesian lexicon (extendable) -------------------
vader_indo = {
    # Positive kata-kata umum dalam bahasa Indonesia beserta bobot positifnya
    "bagus": 2.5, "sangat bagus": 3.5, "baik": 2.2, "sangat baik": 3.3,
    "luar biasa": 4.0, "hebat": 3.0, "keren": 2.8, "mantap": 3.0,
    "ramah": 2.6, "profesional": 2.4, "cepat": 2.2, "tepat": 2.0,
    "bersih": 2.1, "nyaman": 2.4, "menyenangkan": 2.6, "memuaskan": 3.0,
    "puas": 2.8, "terbaik": 3.5, "rekomendasi": 3.2, "recommended": 3.2,
    "favorit": 2.5, "bagus sekali": 3.6, "sempurna": 3.8, "ramah sekali": 3.2,
    "mantul": 3.0, "mantep": 3.0, "jos": 2.5,

    # Weak positive (positif lemah)
    "lumayan": 1.2, "cukup baik": 1.5, "oke": 1.4, "ok": 1.3,

    # Negative kata-kata negatif
    "buruk": -2.8, "sangat buruk": -3.5, "jelek": -2.5, "jelek banget": -3.4,
    "payah": -2.4, "parah": -2.8, "menyedihkan": -3.2, "kecewa": -2.6,
    "mengecewakan": -2.9, "kotor": -2.7, "berantakan": -2.4,
    "lambat": -2.0, "tidak ramah": -2.8, "kasar": -2.6, "tidak profesional": -2.8,
    "tidak nyaman": -2.4, "pelayanan buruk": -3.0, "tidak jelas": -2.0,

    # Negation words → mempengaruhi kata di dekatnya
    "tidak": -0.75, "bukan": -0.75, "kurang": -0.6, "nggak": -0.75, "gak": -0.75, "ga": -0.75,

    # Intensifiers → memperkuat makna
    "sangat": 0.8, "banget": 0.9, "sekali": 0.7, "terlalu": 0.6, "super": 1.0,

    # Diminishers → melemahkan makna
    "agak": -0.3, "sedikit": -0.3,
}

sia.lexicon.update(vader_indo)  # Tambahkan lexicon bahasa Indonesia ke VADER

# ------------------- Kamus Sentimen Custom -------------------
custom_dict = {
    # Positive
    "bagus": 1.0, "sangat bagus": 1.0, "baik": 1.0, "sangat baik": 1.0,
    "luar biasa": 1.0, "hebat": 1.0, "mantap": 1.0, "keren": 1.0,
    "ramah": 1.0, "bersih": 1.0, "nyaman": 1.0, "rapi": 1.0,
    "cepat": 1.0, "tepat": 1.0, "membantu": 1.0, "profesional": 1.0,
    "menyenangkan": 1.0, "puas": 1.0, "memuaskan": 1.0,
    "bagus sekali": 1.0, "terbaik": 1.0, "recommended": 1.0,
    "favorit": 1.0, "menarik": 1.0, "ramah sekali": 1.0,

    # Weak Positive
    "lumayan": 0.4, "cukup baik": 0.4, "oke": 0.4, "ok": 0.4,

    # Neutral
    "biasa": 0.0, "standar": 0.0, "normal": 0.0,

    # Negative
    "buruk": -1.0, "jelek": -1.0, "tidak baik": -1.0,
    "tidak bagus": -1.0, "menyedihkan": -1.0, "parah": -1.0,
    "payah": -1.0, "kasar": -1.0, "tidak sopan": -1.0,
    "kotor": -1.0, "berantakan": -1.0, "lambat": -1.0,
    "mengecewakan": -1.0, "kecewa": -1.0,
    "tidak nyaman": -1.0, "tidak ramah": -1.0, "pelayanan buruk": -1.0,
    "jelek banget": -1.0, "sangat buruk": -1.0,
}

# ------------------- Koreksi typo dan bahasa gaul -------------------
corrections = {
    "banguus": "bagus",
    "baikk": "baik",
    "jelekx": "jelek",
    "parrah": "parah",
    "rammah": "ramah",
    "mantap jiwa": "mantap",
    "the best": "terbaik",
    "rekomen": "recommended",
    "nggak bagus": "tidak bagus",
    "ga bagus": "tidak bagus",
    "gak bagus": "tidak bagus",
    "nggak baik": "tidak baik",
    "ga baik": "tidak baik",
}

# ------------------- Koreksi frasa negatif -------------------
phrase_corrections = {
    "tidak terlalu bagus": "kurang bagus",
    "tidak terlalu baik": "kurang baik",
    "tidak begitu baik": "kurang baik",
    "tidak begitu bagus": "kurang bagus",
    "tidak memuaskan": "kurang memuaskan",
    "tidak cepat": "lambat",
    "tidak ramah": "kurang ramah",
    "tidak nyaman": "kurang nyaman",
    "tidak bersih": "kotor",
    "tidak enak dilihat": "jelek",
    "tidak profesional": "kurang profesional",
    "tidak membantu": "tidak membantu",
}

# ------------------- Stopwords -------------------
stopwords = [
    "yang", "dan", "atau", "di", "ke", "dari", "itu", "ini",
    "saya", "kami", "kita", "dia", "mereka",
    "ada", "adalah", "untuk", "dengan", "sebagai",
    "jadi", "karena", "bahwa", "agar"
]

# ------------------- Helper: replace kata dengan batas kata -------------------
def _replace_word_with_boundary(text: str, old: str, new: str) -> str:
    pattern = r"\b" + re.escape(old) + r"\b"
    return re.sub(pattern, new, text, flags=re.IGNORECASE)

# ------------------- Bersihkan teks -------------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    for old, new in phrase_corrections.items():
        text = _replace_word_with_boundary(text, old, new)
    for old, new in corrections.items():
        text = _replace_word_with_boundary(text, old, new)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = [w for w in re.split(r"\s+", text) if w and w not in stopwords]
    return " ".join(words)

# ------------------- Versi ideal custom_sentiment_score -------------------
def custom_sentiment_score(text: str) -> float:
    if not text:
        return 0.0
    total = 0.0
    count = 0
    t = text.lower()
    INTENSIFIERS = ["banget", "sekali", "sangat", "super", "terlalu"]

    for phrase, score in custom_dict.items():
        pattern = r"\b" + re.escape(phrase) + r"\b"
        matches = re.findall(pattern, t)
        if matches:
            cnt = len(matches)
            total += score * cnt
            count += cnt
            t = re.sub(pattern, " ", t)

    for word in t.split():
        if word in INTENSIFIERS:
            total += 1.0
            count += 1

    if count == 0:
        return 0.0
    return total / count

# ------------------- Normalisasi kata Indonesia → Inggris (fallback TextBlob) -------------------
NORMALIZE_MAP = {
    "bagus": "good",
    "baik": "good",
    "mantap": "great",
    "puas": "satisfied",
    "ramah": "friendly",
    "cepat": "fast",
    "bersih": "clean",
    "buruk": "bad",
    "jelek": "bad",
    "lambat": "slow",
    "kotor": "dirty",
    "kecewa": "disappointed",
    "mengecewakan": "disappointing",
}

# ------------------- Deteksi sentimen versi ideal -------------------
def detect_sentiment(text: str):
    if not text or not text.strip():
        return 0.0, 0.0

    cleaned = clean_text(text)
    text_lower = cleaned.lower()

    positive_count = 0
    total_detected = 0
    INTENSIFIERS = ["banget", "sekali", "sangat", "super", "terlalu"]

    for phrase in sorted(custom_dict.keys(), key=len, reverse=True):
        pattern = r"\b" + re.escape(phrase) + r"\b"
        matches = re.findall(pattern, text_lower)
        if matches:
            cnt = len(matches)
            total_detected += cnt
            if custom_dict[phrase] > 0:
                positive_count += cnt
            text_lower = re.sub(pattern, " ", text_lower)

    for word in text_lower.split():
        total_detected += 1
        if word in INTENSIFIERS:
            positive_count += 1
        else:
            tb_word = NORMALIZE_MAP.get(word, word)
            try:
                if TextBlob(tb_word).sentiment.polarity > 0:
                    positive_count += 1
            except Exception:
                pass

    if total_detected == 0:
        pos_pct = 0
    else:
        ratio = positive_count / total_detected
        pos_pct = 100 if ratio >= 0.6 else ratio * 100

    try:
        vader_score = sia.polarity_scores(cleaned)["compound"]
    except Exception:
        vader_score = 0.0

    return pos_pct, vader_score

# ------------------- Koreksi kalimat negatif -------------------
def correct_negative_sentence(sentence: str):
    if not sentence:
        return False, sentence
    corrected = sentence.lower()
    found = False
    for neg, pos in phrase_corrections.items():
        pattern = r"\b" + re.escape(neg) + r"\b"
        if re.search(pattern, corrected):
            corrected = re.sub(pattern, pos, corrected)
            found = True
    for neg, pos in corrections.items():
        pattern = r"\b" + re.escape(neg) + r"\b"
        if re.search(pattern, corrected):
            corrected = re.sub(pattern, pos, corrected)
            found = True
    try:
        vader_score = sia.polarity_scores(clean_text(sentence))['compound']
    except Exception:
        vader_score = 0.0
    if found or vader_score < 0:
        return True, corrected.capitalize()
    return False, sentence
