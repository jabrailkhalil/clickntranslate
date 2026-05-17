import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageInfo:
    code: str
    english_name: str
    russian_name: str
    short_label: str
    flag_icon: str
    windows_ocr_tag: str
    tesseract_code: str
    google_code: str = ""
    lingva_code: str = ""
    libre_code: str = ""
    mymemory_code: str = ""

    def display_name(self, interface_language="en"):
        return self.russian_name if interface_language == "ru" else self.english_name


LANGUAGES = [
    LanguageInfo("en", "English", "Английский", "EN", "American_flag.png", "en-US", "eng"),
    LanguageInfo("ru", "Russian", "Русский", "RU", "Russian_flag.png", "ru-RU", "rus"),
    LanguageInfo("de", "German", "Немецкий", "DE", "German_flag.png", "de-DE", "deu"),
    LanguageInfo("fr", "French", "Французский", "FR", "French_flag.png", "fr-FR", "fra"),
    LanguageInfo("es", "Spanish", "Испанский", "ES", "Spanish_flag.png", "es-ES", "spa"),
    LanguageInfo("it", "Italian", "Итальянский", "IT", "Italian_flag.png", "it-IT", "ita"),
    LanguageInfo("pt", "Portuguese", "Португальский", "PT", "Portuguese_flag.png", "pt-BR", "por"),
    LanguageInfo("pl", "Polish", "Польский", "PL", "Polish_flag.png", "pl-PL", "pol"),
    LanguageInfo("uk", "Ukrainian", "Украинский", "UK", "Ukrainian_flag.png", "uk-UA", "ukr"),
    LanguageInfo("tr", "Turkish", "Турецкий", "TR", "Turkish_flag.png", "tr-TR", "tur"),
    LanguageInfo("nl", "Dutch", "Нидерландский", "NL", "Dutch_flag.png", "nl-NL", "nld"),
    LanguageInfo("zh", "Chinese", "Китайский", "ZH", "Chinese_flag.png", "zh-CN", "chi_sim", google_code="zh-CN", mymemory_code="zh-CN"),
    LanguageInfo("ja", "Japanese", "Японский", "JA", "Japanese_flag.png", "ja-JP", "jpn"),
    LanguageInfo("ko", "Korean", "Корейский", "KO", "Korean_flag.png", "ko-KR", "kor"),
    LanguageInfo("ar", "Arabic", "Арабский", "AR", "Arabic_flag.png", "ar-SA", "ara"),
    LanguageInfo("hi", "Hindi", "Хинди", "HI", "Hindi_flag.png", "hi-IN", "hin"),
]

LANGUAGE_BY_CODE = {language.code: language for language in LANGUAGES}


def get_language(code):
    return LANGUAGE_BY_CODE.get((code or "").lower())


def language_display_name(code, interface_language="en"):
    language = get_language(code)
    return language.display_name(interface_language) if language else str(code or "").upper()


def language_english_name(code):
    language = get_language(code)
    return language.english_name if language else str(code or "")


def language_short_label(code):
    language = get_language(code)
    return language.short_label if language else str(code or "").upper()


def language_icon_path(code):
    language = get_language(code)
    if not language:
        return ""
    return "icons/" + language.flag_icon


def language_names(interface_language="en"):
    return [language.display_name(interface_language) for language in LANGUAGES]


def language_code_from_name(name, interface_language="en"):
    name = str(name or "")
    for language in LANGUAGES:
        if name in (language.english_name, language.russian_name):
            return language.code
    normalized = name.strip().lower()
    for language in LANGUAGES:
        if normalized == language.code:
            return language.code
    return "en" if interface_language == "en" else "ru"


def windows_ocr_tag(code):
    language = get_language(code)
    return language.windows_ocr_tag if language else str(code or "en-US")


def tesseract_language_code(code):
    if code == "universal":
        return "eng+rus"
    language = get_language(code)
    return language.tesseract_code if language else "eng"


def translator_api_code(code, engine):
    language = get_language(code)
    if not language:
        return str(code or "")
    engine = (engine or "").lower()
    if engine == "google":
        return language.google_code or language.code
    if engine == "lingva":
        return language.lingva_code or language.google_code or language.code
    if engine == "libretranslate":
        return language.libre_code or language.google_code or language.code
    if engine == "mymemory":
        return language.mymemory_code or language.google_code or language.code
    return language.code


def default_target_for_source(source_code, preferred_target=None):
    source_code = (source_code or "en").lower()
    preferred_target = (preferred_target or "").lower()
    if preferred_target and preferred_target != source_code and preferred_target in LANGUAGE_BY_CODE:
        return preferred_target
    if source_code in {"auto", "universal"}:
        return "ru"
    if source_code != "ru":
        return "ru"
    return "en"


_LATIN_STOPWORDS = {
    "en": {
        "the", "and", "that", "this", "with", "for", "you", "your", "are", "is", "was", "were",
        "have", "has", "not", "from", "to", "of", "in", "on", "settings", "translate", "translation",
        "file", "open", "save", "cancel", "close", "hello", "world",
    },
    "de": {
        "der", "die", "das", "und", "ist", "nicht", "mit", "fur", "für", "ein", "eine", "ich",
        "sie", "auf", "zu", "von", "den", "dem", "werden", "ubersetzen", "übersetzen", "datei",
        "speichern", "offnen", "öffnen",
    },
    "fr": {
        "le", "la", "les", "des", "du", "un", "une", "et", "est", "pas", "pour", "dans", "que",
        "avec", "vous", "nous", "traduire", "traduction", "fichier", "ouvrir", "enregistrer",
        "fermer",
    },
    "es": {
        "el", "la", "los", "las", "de", "del", "que", "con", "para", "por", "una", "uno", "está",
        "esta", "este", "traducir", "traduccion", "traducción", "archivo", "abrir", "guardar",
        "cerrar",
    },
    "it": {
        "il", "lo", "la", "gli", "le", "di", "che", "con", "per", "una", "uno", "sono", "non",
        "tradurre", "traduzione", "file", "aprire", "salvare", "chiudere",
    },
    "pt": {
        "o", "a", "os", "as", "de", "do", "da", "que", "com", "para", "por", "uma", "um", "não",
        "nao", "traduzir", "traducao", "tradução", "arquivo", "abrir", "salvar", "fechar",
    },
    "pl": {
        "i", "oraz", "jest", "nie", "dla", "się", "sie", "ten", "ta", "to", "plik", "otwórz",
        "otworz", "zapisz", "zamknij", "tlumacz", "tłumacz", "tłumaczenie", "tlumaczenie",
    },
    "tr": {
        "ve", "bir", "bu", "için", "icin", "degil", "değil", "ile", "dosya", "aç", "ac", "kaydet",
        "kapat", "çevir", "cevir", "çeviri", "ceviri",
    },
    "nl": {
        "de", "het", "een", "en", "is", "niet", "voor", "met", "van", "op", "bestand", "openen",
        "opslaan", "sluiten", "vertalen", "vertaling",
    },
}

_CYRILLIC_STOPWORDS = {
    "ru": {
        "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все",
        "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по", "только",
        "перевод", "перевести", "файл", "открыть", "сохранить", "закрыть", "настройки",
    },
    "uk": {
        "і", "й", "в", "не", "що", "він", "на", "я", "з", "як", "а", "то", "все", "вона",
        "так", "його", "але", "ти", "до", "у", "за", "по", "тільки", "переклад",
        "перекласти", "файл", "відкрити", "зберегти", "закрити", "налаштування",
    },
}

_LATIN_CHAR_HINTS = {
    "de": "äöüß",
    "fr": "àâæçéèêëîïôœùûÿ",
    "es": "áéíñóú¿¡",
    "it": "àèéìíîòóù",
    "pt": "áâãàçéêíóôõú",
    "pl": "ąćęłńóśźż",
    "tr": "çğıöşü",
    "nl": "ĳ",
}

_LATIN_PATTERNS = {
    "en": (" th", "ing", "tion", "you", "ver", "wh"),
    "de": ("sch", "ich", "ein", "ung", "nicht", "der "),
    "fr": ("tion", "ment", "qu", "est ", "les ", "des "),
    "es": ("ción", "que", " los ", " las ", " del ", "para"),
    "it": ("zione", "gli", "che", " per ", " della"),
    "pt": ("ção", "ões", " que ", " para", " dos ", " das "),
    "pl": ("sz", "cz", "rz", "prz", "nie", " się"),
    "tr": ("lar", "ler", "yor", "bir", " için", " değil"),
    "nl": ("ij", "sch", "een", "het", "van ", "voor"),
}


def _letter_tokens(text):
    return re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)


def _count_range(text, start, end):
    return sum(1 for ch in text if start <= ch <= end)


def _dominant_script_language(text):
    counts = {
        "ja": _count_range(text, "\u3040", "\u30ff"),
        "ko": _count_range(text, "\uac00", "\ud7af"),
        "zh": _count_range(text, "\u4e00", "\u9fff"),
        "ar": _count_range(text, "\u0600", "\u06ff"),
        "hi": _count_range(text, "\u0900", "\u097f"),
        "cyrillic": _count_range(text, "\u0400", "\u04ff"),
    }
    if counts["ja"]:
        return "ja"
    for code in ("ko", "zh", "ar", "hi"):
        if counts[code] >= 2:
            return code
    if counts["cyrillic"] >= max(2, int(len(text) * 0.12)):
        return _detect_cyrillic_language(text)
    return ""


def _detect_cyrillic_language(text):
    lowered = text.lower()
    ukrainian_unique = sum(lowered.count(ch) for ch in "іїєґ")
    russian_unique = sum(lowered.count(ch) for ch in "ыэёъ")
    if ukrainian_unique and ukrainian_unique >= russian_unique:
        return "uk"
    if russian_unique:
        return "ru"

    tokens = _letter_tokens(lowered)
    scores = {"ru": 0, "uk": 0}
    for token in tokens:
        for code, words in _CYRILLIC_STOPWORDS.items():
            if token in words:
                scores[code] += 3 if len(token) > 2 else 1
    if scores["uk"] > scores["ru"]:
        return "uk"
    return "ru"


def _detect_latin_language(text):
    lowered = " " + text.lower() + " "
    tokens = _letter_tokens(lowered)
    if not tokens:
        return "en"

    scores = {code: 0 for code in _LATIN_STOPWORDS}
    for code, chars in _LATIN_CHAR_HINTS.items():
        scores[code] += sum(lowered.count(ch) for ch in chars) * 5
    for code, words in _LATIN_STOPWORDS.items():
        for token in tokens:
            if token in words:
                scores[code] += 3 if len(token) > 2 else 1
    for code, patterns in _LATIN_PATTERNS.items():
        for pattern in patterns:
            scores[code] += lowered.count(pattern) * 2

    best_code, best_score = max(scores.items(), key=lambda item: item[1])
    second_score = sorted(scores.values(), reverse=True)[1]
    if best_score <= 2:
        return "en"
    if len(tokens) <= 3 and best_score - second_score < 3:
        return "en"
    return best_code


def detect_language_code(text):
    text = str(text or "").strip()
    if not text:
        return "en"
    sample = text[:8000]
    script_language = _dominant_script_language(sample)
    if script_language:
        return script_language
    return _detect_latin_language(sample)

    text = text or ""
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return "zh"
    if any("\u3040" <= ch <= "\u30ff" for ch in text):
        return "ja"
    if any("\uac00" <= ch <= "\ud7af" for ch in text):
        return "ko"
    if any("\u0600" <= ch <= "\u06ff" for ch in text):
        return "ar"
    if any("\u0900" <= ch <= "\u097f" for ch in text):
        return "hi"
    cyrillic_count = sum(1 for ch in text if "\u0400" <= ch <= "\u04ff")
    if cyrillic_count >= max(2, len(text) * 0.2):
        uk_chars = set("іїєґІЇЄҐ")
        if any(ch in uk_chars for ch in text):
            return "uk"
        return "ru"
    lowered = text.lower()
    if any(ch in lowered for ch in "ąćęłńóśźż"):
        return "pl"
    if any(ch in lowered for ch in "ğışİöüç"):
        return "tr"
    if any(ch in lowered for ch in "äöüß"):
        return "de"
    if any(ch in lowered for ch in "àâæçéèêëîïôœùûüÿ"):
        return "fr"
    if any(ch in lowered for ch in "áéíñóúü¿¡"):
        return "es"
    return "en"


def ocr_translate_options(preferred_target=None):
    return [
        (language.code, default_target_for_source(language.code, preferred_target))
        for language in LANGUAGES
    ]
