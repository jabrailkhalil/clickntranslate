# Click’n’Translate for Android

Translate screens, text and photos in one app.

[Русский](README.md) · [Website](https://clickn.dev) · [Telegram](https://t.me/jabrail_digital)

## Android 0.3.2 — preview

- Four destinations: **Screen**, **Text**, **History**, **Settings**.
- A prominent start button, visible language pair and direct service configuration.
- Seven theme thumbnails, including paper Day, Night and Nord, with five accent colors.
- English, Russian, German, French, Spanish and Chinese interface languages.
- Google, Lingva, MyMemory and LibreTranslate, additional API services and offline models.
- Text translation with copy, sharing and local history of up to 50 entries.
- Gallery translation and image sharing from other apps.
- Two setup steps: appearance, then languages and a short usage guide.
- Glossary mode cards and a separate opt-in Japanese sound-effects pack.
- Six static companions and imported pictures for the floating button.
- Reading cards and the button hide after inactivity; pin a result to keep it open.
- Advanced OCR, model, speech, dictionary, glossary and floating-button options.

Requires Android 8.0+ and ARM64. Local LLMs require Android 13+. Root is not needed for the standard capture flow.

[Download preview APK 0.3.2](artifacts/android/README.md) · [Changes and limitations](docs/android-preview-v2.md).

## Setup

Choose a theme thumbnail and interface language, then the translation languages. Setup preserves the existing service; new installations use Google. Overlay permission and screen-capture consent are requested when starting screen translation. Other permission, service and model checks are available on the home screen and in settings.

Google needs no key. MyMemory requires an explicit source language. Lingva accepts a server URL; LibreTranslate accepts a server URL and an optional key. Connection testing sends a sample phrase to the selected service. API keys use the app’s protected credential storage.

Default OCR recognizes Latin, Chinese, Japanese and Korean scripts. Choose a suitable OCR service for other scripts. Download offline models before use. Translation language support depends on the selected service.

The help button reopens setup. Text and image translation work without screen-capture permission. Share a Telegram message to Clickn to translate its text without OCR. Text history stays on the device, is excluded from backup and can be cleared on the History tab.

## Build

Use JDK 17, Android SDK 35, Build Tools 35.0.0, NDK 26.1.10909125 and CMake 3.22.1. Set the SDK path in `local.properties` (see `local.properties.example`). Ninja must also be on PATH for the host Vulkan shader generator; the Android SDK CMake `bin` directory contains it.

```bash
git submodule update --init --recursive
./gradlew :app:assembleDebug :app:lintDebug :app:testDebugUnitTest --continue
```

On Windows use `gradlew.bat`. APK: `app/build/outputs/apk/debug/app-debug.apk`. Package: `dev.clickn.translate`; debug package: `dev.clickn.translate.debug`.

The `android` branch is for development and manual testing. Automatic release publishing is disabled. Desktop development remains on `main`.

[Validation and limitations](docs/android-testing.md) · [Development](CONTRIBUTING.md)
