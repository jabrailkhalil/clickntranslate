# Click’n’Translate on Android

[Download APK 1.8.2](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/ClicknTranslate-1.8.2-arm64.apk) · [Русский](ANDROID.ru.md) · [Main README](../README.md#android)

Translate games and other apps using a floating button, translate a photo from your gallery, or type, paste and share text. The Android app runs on the phone independently of the desktop app. Standard screen capture needs no root access.

## Install and start

1. Install the APK on an **Android 8.0+ ARM64** phone or tablet. Android may ask you to allow installation from your browser or file manager.
2. Choose the **interface language**, **theme** and **translation languages** in the first-run guide. The guide can be reopened from Help. New installations use Google; it needs an internet connection but no API key.
3. On the home screen, start screen translation. Grant **display over other apps** and approve Android’s screen-capture prompt. On **Android 14+**, choose the **entire screen** to translate in other apps.
4. Open a game or another app. In full-screen mode, tap the floating button to capture, recognize and translate the screen. Hold the button to open its menu. Result placement and appearance can be adjusted in settings.

Text and gallery translation do not require screen capture. Accessibility is needed only for additional actions such as input translation or volume-button control; it is not required for basic screen translation. Protected screens may block capture.

## Choose how to translate

| Task | How it works |
| --- | --- |
| Translate the screen | Tap the floating button in full-screen mode; the result appears over the current app. |
| Translate a region | Hold the button, choose **Region**, draw the area and confirm. The selected area is remembered. |
| Follow changing dialogue | Select repeat translation from the floating menu, then tap the main button to start or stop. Settings control the interval or when the image/text has settled. |
| Translate typed or copied text | Open **Text**, choose the languages, type or paste, then translate. Copy or share the result. |
| Translate text from another app | Use Android’s **Share → Clickn** action when the source app supports sharing text. This sends text directly, without OCR. |
| Translate a photo or screenshot | Choose **Image** on the home screen, or share an image to Clickn from another app. |
| Return to a text translation | Open **History**. Text history keeps up to 50 entries locally and can be cleared. |

To clear a remembered region, hold the floating button → **Region** → **Redraw**, then **double-tap the screen without drawing a rectangle**. The next full-screen capture uses the whole screen. If the button is in word-selection mode, switch it to **Full-screen Translate** in its menu as well.

If the floating button hides after inactivity, use **Show button** in the app or capture notification. **Keep the button visible** makes it persistent. Use **Stop** in the app or capture notification to end capture.

## Online, offline and API services

- **Online:** Google, Lingva, MyMemory and LibreTranslate. Public services need a connection and may limit requests. MyMemory needs an explicit source language; Lingva and LibreTranslate allow a custom server.
- **Offline translation:** select **ML Kit**, choose an explicit source language and download the supported language models before going offline. The available language pairs depend on the service.
- **Your own API:** configure the chosen service in Settings. Credentials use the app’s protected storage. Availability, model capabilities, fees and rate limits depend on the provider.
- **OCR:** the default bundled recognizers cover Latin, Chinese, Japanese and Korean scripts. Other scripts, including Cyrillic and Arabic, need a suitable alternative OCR engine/service. Choosing a translation target does not add OCR support for that script. Shared text bypasses OCR.

The usual screen workflow is **capture → OCR → translation → overlay**. Local OCR keeps recognition on the device; online translation sends recognized text to the chosen service. A configured cloud OCR or image-capable API may receive the captured image. Offline translation remains local after its models are downloaded. See [Privacy](../PRIVACY.md).

## Make it comfortable

Android 1.8.2 has six interface languages: English, Russian, German, French, Spanish and Chinese. Choose light, dark, AMOLED or paper themes, customize the floating button and select Chester, Doc, Pancake, Raf, Lola or your own picture. Android companions are static images. Translation languages are separate from interface languages and depend on the selected service.

If translation does not appear, check the source/target languages, service connection, OCR script support and screen-capture consent. If capture stops in the background, check the phone’s battery restrictions. Report the phone model, Android version, app version, OCR, translation service and reproduction steps via [GitHub Issues](https://github.com/jabrailkhalil/clickntranslate/issues) or [Telegram](https://t.me/jabrail_digital); do not include API keys.

[Android source and build instructions](https://github.com/jabrailkhalil/clickntranslate/tree/android) · [All release downloads](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.2)
