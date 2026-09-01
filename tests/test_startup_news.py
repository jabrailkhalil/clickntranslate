import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets

import main


_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


class _NewsOwner(QtWidgets.QWidget):
    _maybe_show_startup_news = main.DarkThemeApp._maybe_show_startup_news

    def __init__(self, seen_id="", seen_version="", language="ru"):
        super().__init__()
        self.current_interface_language = language
        self.current_theme = "Темная"
        self.config = {
            "last_seen_startup_news_id": seen_id,
            "last_seen_startup_news_version": seen_version,
        }
        self._startup_news_dialog = None
        self.saved = 0
        self.guide_checks = 0

    def save_config(self):
        self.saved += 1

    def _maybe_start_first_run_guide(self):
        self.guide_checks += 1


def test_startup_news_is_localized_and_explains_user_benefits():
    download_words = {
        "en": "downloads",
        "ru": "скачиван",
        "es": "descargas",
        "de": "downloads",
        "fr": "téléchargements",
        "zh": "下载",
    }
    user_words = {
        "en": "users",
        "ru": "пользовател",
        "es": "usuarios",
        "de": "nutzer",
        "fr": "utilisateurs",
        "zh": "用户",
    }
    for language in ("en", "ru", "es", "de", "fr", "zh"):
        text = main.startup_news_text(language)
        assert len(text["changes"]) == 4
        assert text["promise"]
        assert text["continue"]
        assert "000" in f"{text['title']} {text['intro']}"
        milestone = f"{text['window']} {text['title']} {text['intro']}".lower()
        assert download_words[language] in milestone
        assert user_words[language] not in milestone
        html = main.startup_news_html(language, "9.9.9")
        assert "9.9.9" in html
        assert text["title"] in html
        assert text["promise"] in html
        for item in text["changes"]:
            assert item in html


def test_startup_news_is_shown_once_per_announcement_and_remembered():
    app = _app()
    owner = _NewsOwner()
    owner.show()

    owner._maybe_show_startup_news()
    app.processEvents()

    dialog = owner._startup_news_dialog
    assert dialog is not None
    assert dialog.isVisible()
    assert main.APP_VERSION in dialog.windowTitle()
    assert main.startup_news_text("ru")["promise"] in dialog.text()

    dialog.accept()
    app.processEvents()
    assert owner.config["last_seen_startup_news_id"] == main.STARTUP_NEWS_ID
    assert owner.config["last_seen_startup_news_version"] == main.APP_VERSION
    assert owner.saved == 1
    assert owner._startup_news_dialog is None

    owner._maybe_show_startup_news()
    app.processEvents()
    assert owner._startup_news_dialog is None
    assert owner.saved == 1
    owner.close()


def test_acknowledged_announcement_never_opens_again():
    _app()
    owner = _NewsOwner(seen_id=main.STARTUP_NEWS_ID, seen_version="old-version")
    owner._maybe_show_startup_news()
    assert owner._startup_news_dialog is None
    assert owner.saved == 0
    owner.close()


def test_same_version_does_not_hide_a_new_announcement_id():
    app = _app()
    owner = _NewsOwner(seen_id="previous-announcement", seen_version=main.APP_VERSION)

    owner._maybe_show_startup_news()
    app.processEvents()

    assert owner._startup_news_dialog is not None
    owner._startup_news_dialog.reject()
    app.processEvents()
    owner.close()


def test_dialog_uses_the_current_application_interface_language():
    app = _app()
    for language in ("en", "ru", "es", "de", "fr", "zh"):
        owner = _NewsOwner(language=language)
        owner._maybe_show_startup_news()
        app.processEvents()
        dialog = owner._startup_news_dialog
        text = main.startup_news_text(language)
        assert text["title"] in dialog.text()
        assert dialog.windowTitle() == text["window"].format(version=main.APP_VERSION)
        dialog.reject()
        app.processEvents()
        owner.close()
