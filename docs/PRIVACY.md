# Click'n'Translate Privacy Policy

Effective date: October 24, 2026

Click'n'Translate is a screen OCR and translation application published by Jabrail Digital. This policy describes the Windows, macOS and Linux desktop edition. The application does not require a Click'n'Translate account and does not include advertising, analytics, or developer-operated telemetry.

The project also provides a separate Android edition. Its screen capture,
online/offline processing and local history are described in the
[Android data and permissions guide](docs/ANDROID.md#data-and-permissions).
The product website is [translate.clickn.dev](https://translate.clickn.dev/);
website privacy information is available from [clickn.dev](https://clickn.dev/en/privacy/).

## Data processed by the application

- Screen images are captured only after a user invokes an OCR or translation action. Local OCR engines process those images on the device. If the user selects a vision API and enables image input, the selected image is sent to that configured provider for recognition or translation.
- Clipboard text is read or written only for features explicitly invoked or enabled by the user.
- Copy and translation histories are optional. When enabled, they are stored locally on the user's device.
- Settings, caches, downloaded OCR files, and offline translation models are stored locally on the user's device.

## Online translation providers

When an online translation engine is selected, the text the user asks to translate is sent to that provider so it can return a translation. Available engines include Google Translate, MyMemory, Lingva and LibreTranslate instances. User-configured API connections include OpenAI, Gemini, Anthropic, DeepL, LibreTranslate and compatible custom endpoints. Vision-capable API connections can also receive selected images when image input is enabled. Their handling of submitted text and images is governed by their own terms and privacy policies.

API keys use the operating system credential store when available, with an in-memory session fallback if persistent secure storage is unavailable. Keys are excluded from settings exports and diagnostic reports. Custom API addresses determine which server receives the configured request; keys are not forwarded automatically to redirects or a fallback provider.

Argos Translate and Hy-MT are offline options. After their selected packages are downloaded, translation is performed on the user's device.

## Downloads and network access

The application uses network access for online translation, update checks outside the Microsoft Store build, and user-requested downloads of optional OCR engines, OCR language data, and offline translation packages. Microsoft Store builds receive application updates through Microsoft Store.

## Retention and deletion

Click'n'Translate does not send history or settings to Jabrail Digital. Users can clear caches and histories from the application. Uninstalling the Microsoft Store package removes its package-local application data according to Windows settings and policy.

## Contact

Questions and privacy requests can be submitted through [GitHub Issues](https://github.com/jabrailkhalil/clickntranslate/issues) or Telegram [@jabrail_digital](https://t.me/jabrail_digital).
