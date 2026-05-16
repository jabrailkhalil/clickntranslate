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
    if source_code != "ru":
        return "ru"
    return "en"


def detect_language_code(text):
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
