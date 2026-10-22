# Продолжение работы с Click’n’Translate

Актуальная ветка: `codex/pets-mascots`, Python-версия 1.8.2.
Изменения интерфейса и маскотов находятся в PR #6; функции PR #7 уже включены.

## Получить исходники

```powershell
git clone --branch codex/pets-mascots https://github.com/jabrailkhalil/clickntranslate.git
cd clickntranslate
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt pytest
```

Для Linux и macOS см. [LINUX.md](LINUX.md) и [MACOS.md](MACOS.md).

## Запуск без сборки

```powershell
.venv\Scripts\python.exe tools/run_mascot_app.py
```

Запускается настоящее приложение с отдельным профилем `.tmp/mascot-app`.
Горячие клавиши и перевод доступны; настройки автозапуска ОС не изменяются.

## Маскоты

Используется оригинальный набор Pets v18: Клик, Док, Честер, Блинчик, Раф и Лола.
На главном экране один статичный ярлык выбранного персонажа. Семь стационарных
анимаций и шестнадцать направлений взгляда работают на рабочем столе и в настройках.

- [Формат, сценарии и изображения](mascots/pets-v18/README.md).
- [Промпты генерации](mascots/pets-v18/PROMPTS.md).
- [Проверки](mascots/pets-v18/TESTING.md).
- Просмотр: `python tools/preview_mascots.py`.
- Экспорт анимаций: `python tools/qa_mascot_motion.py OUTPUT_DIRECTORY`.

## Проверка изменений

```powershell
.venv\Scripts\python.exe tools/run_ci_tests.py --parts 8 --timeout 160
```

Проверки используют изолированные данные. Точные результаты последнего прогона
сохранены в `docs/mascots/pets-v18/test-summary.json`.
