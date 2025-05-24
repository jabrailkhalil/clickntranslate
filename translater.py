import argostranslate.package
import argostranslate.translate

def install_models():
    print("Обновление индекса пакетов...")
    argostranslate.package.update_package_index()
    available_packages = argostranslate.package.get_available_packages()
    ru_en_package = None
    en_ru_package = None
    for pkg in available_packages:
        if pkg.from_code == "ru" and pkg.to_code == "en":
            ru_en_package = pkg
        elif pkg.from_code == "en" and pkg.to_code == "ru":
            en_ru_package = pkg
    if ru_en_package:
        print(f"Найден пакет RU->EN: {ru_en_package}")
        download_path = ru_en_package.download()
        argostranslate.package.install_from_path(download_path)
        print("Пакет RU->EN установлен.")
    else:
        print("Пакет перевода для RU->EN не найден.")
    if en_ru_package:
        print(f"Найден пакет EN->RU: {en_ru_package}")
        download_path = en_ru_package.download()
        argostranslate.package.install_from_path(download_path)
        print("Пакет EN->RU установлен.")
    else:
        print("Пакет перевода для EN->RU не найден.")

def test_translation():
    installed_languages = argostranslate.translate.get_installed_languages()
    ru_language = None
    en_language = None
    for language in installed_languages:
        if language.code == "ru":
            ru_language = language
        elif language.code == "en":
            en_language = language
    if ru_language is None or en_language is None:
        print("Модели перевода для ru<->en не установлены.")
        print("Пожалуйста, установите языковые модели через Argos Translate.")
        return
    # Пробуем RU->EN
    translation_ru_en = ru_language.get_translation(en_language)
    # Пробуем EN->RU
    translation_en_ru = en_language.get_translation(ru_language)
    text_ru = "Привет, мир!"
    text_en = "Hello, world!"
    if translation_ru_en is not None:
        print("RU->EN:", translation_ru_en.translate(text_ru))
    else:
        print("Нет модели для RU->EN")
    if translation_en_ru is not None:
        print("EN->RU:", translation_en_ru.translate(text_en))
    else:
        print("Нет модели для EN->RU")

def translate_text(text, source_code, target_code):
    installed_languages = argostranslate.translate.get_installed_languages()
    source_language = None
    target_language = None
    for language in installed_languages:
        if language.code == source_code:
            source_language = language
        elif language.code == target_code:
            target_language = language
    if source_language is None or target_language is None:
        raise Exception(f"Модели перевода не установлены для: {source_code}->{target_code}")
    translation_obj = source_language.get_translation(target_language)
    if translation_obj is None:
        raise Exception(f"Нет модели для перевода {source_code}->{target_code}. Проверьте, что установлены обе модели (RU->EN и EN->RU) через Argos Translate.")
    return translation_obj.translate(text)

if __name__ == '__main__':
    install_models()
    print("Попытка тестового перевода:")
    test_translation()