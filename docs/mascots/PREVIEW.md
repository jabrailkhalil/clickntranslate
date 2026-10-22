# Просмотр актуальных маскотов

Приложение использует оригинальные цельные кадры Pets v18.
[Описание набора и сценариев](pets-v18/README.md).

```powershell
.venv\Scripts\python.exe tools/preview_mascots.py
.venv\Scripts\python.exe tools/run_mascot_app.py
```

Первый инструмент показывает шесть персонажей и семь стационарных анимаций.
Второй открывает настоящее приложение с отдельным профилем.

Для экспорта анимаций и статичных поз:

```powershell
.venv\Scripts\python.exe tools/qa_mascot_motion.py OUTPUT_DIRECTORY
```

Исходные атласы находятся в `src/icons/desktop-assistant/<персонаж>/pets-v2.png`.
Промпты и результаты проверки сохранены в [pets-v18](pets-v18/).
Ярлыки `compare-mascots.cmd`, `preview-orbit.cmd` и `preview-pancake-cycle.cmd`
открывают актуальный инструмент `tools/preview_mascots.py`.
