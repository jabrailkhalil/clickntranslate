import argostranslate.package
import argostranslate.translate

def install_ru_en_model():
    # Обновление индекса пакетов (списка доступных языковых моделей)
    print("Обновление индекса пакетов...")
    argostranslate.package.update_package_index()

    # Получение списка доступных пакетов
    available_packages = argostranslate.package.get_available_packages()
    ru_en_package = None
    for pkg in available_packages:
        # Фильтрация пакетов для перевода с русского (ru) на английский (en)
        if pkg.from_code == "en" and pkg.to_code == "ru":
            ru_en_package = pkg
            break

    if ru_en_package is None:
        print("Пакет перевода для ru->en не найден.")
        return

    print(f"Найден пакет: {ru_en_package}")
    # Скачивание пакета в локальную файловую систему
    download_path = ru_en_package.download()
    # Установка пакета из скачанного файла
    argostranslate.package.install_from_path(download_path)
    print("Пакет установлен.")

def test_translation():
    # Получаем список установленных языков
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

    # Получаем переводчик для пары RU -> EN
    translation = ru_language.get_translation(en_language)
    text_ru = "By running this code, you will get a working text editor with support for hot keys. Hot keys"
    translated_text = translation.translate(text_ru)

    print("Исходный текст (RU):", text_ru)
    print("Перевод (EN):", translated_text)

def translate_text(text, source_code, target_code):
    """
    Переводит заданный текст с использованием установленных языковых моделей.
    :param text: Исходный текст для перевода
    :param source_code: Код исходного языка (например, "ru" или "en")
    :param target_code: Код целевого языка
    :return: Переведённый текст
    """
    installed_languages = argostranslate.translate.get_installed_languages()
    source_language = None
    target_language = None
    for language in installed_languages:
        if language.code == source_code:
            source_language = language
        elif language.code == target_code:
            target_language = language
    if source_language is None or target_language is None:
        raise Exception("Модели перевода не установлены.")
    translation_obj = source_language.get_translation(target_language)
    return translation_obj.translate(text)

if __name__ == '__main__':
    install_ru_en_model()
    print("Попытка тестового перевода:")
    test_translation()
