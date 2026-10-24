<p align="center">
  <img src="../../src/icons/icon.png" alt="" width="72" height="72">
</p>

<h1 align="center">Click’n’Translate</h1>

<a name="readme-languages"></a>

<p align="center">
  <a href="../../README.md">English</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.fr.md">Français</a> ·
  <strong>简体中文</strong> ·
  <a href="README.pt.md">Português</a> ·
  <a href="README.it.md">Italiano</a>
</p>

<p align="center"><strong>用自己的语言，读懂屏幕上的文字。</strong></p>
<p align="center">Windows · macOS · Linux · <a href="#android">Android</a></p>

<p align="center">
  <a href="https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.2"><img src="https://img.shields.io/github/v/release/jabrailkhalil/clickntranslate?style=flat&amp;label=release&amp;color=73529a" alt="Latest release"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/jabrailkhalil/clickntranslate/releases"><img src="https://img.shields.io/github/downloads/jabrailkhalil/clickntranslate/total?style=flat&amp;label=downloads&amp;color=73529a" alt="GitHub release downloads"></a>
</p>

<p align="center">
  <strong><a href="#download">下载</a></strong>
  &nbsp;&nbsp;&nbsp;
  <a href="https://translate.clickn.dev/en/">网站</a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://t.me/jabrail_digital">Telegram</a>
</p>

翻译游戏、提取图片文字、阅读文档，或将消息替换为译文。面向 **Windows、macOS 和 Linux** 的免费开源桌面应用，另有独立的 **Android** 版本。

<p align="center">
  <img src="../../docs/images/translation-demo-v2.gif" alt="用自己的语言，读懂屏幕上的文字。" width="640">
</p>

<a name="download"></a>

## 下载 1.8.2

| 系统 | 安装 | 便携版 |
| --- | --- | --- |
| **Windows** 10/11 · x64 | [EXE](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-x64-installer.exe) | [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-portable-x64.zip) |
| **macOS** 13.4+ · Apple Silicon (M1+) | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-arm64.dmg) | — |
| **macOS** 13.4+ · Intel | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-x86_64.dmg) | — |
| **Linux** · x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.AppImage) | [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.tar.gz) |
| **Android** 8.0+ · ARM64 | [APK](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/ClicknTranslate-1.8.2-arm64.apk) | — |

[全部下载](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.2)

<a name="android"></a>

## Android：无需离开当前应用即可翻译

**用悬浮按钮翻译游戏和应用，也能翻译文字与照片。** 应用直接在手机上运行，无需电脑或 root 权限。

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../images/android-home-dark-1.8.2.png">
    <img src="../images/android-home-light-1.8.2.png" alt="Android 主界面：翻译语言、屏幕翻译、图片翻译与文字翻译" width="280">
  </picture>
</p>

<p align="center"><sub>Android 1.8.2 界面，图中使用俄语。支持包括中文在内的六种界面语言。</sub></p>

1. **安装 APK**，需要 Android 8.0 及以上版本的 ARM64 设备。选择界面语言、主题和翻译语言。
2. **启动屏幕翻译。** 授予悬浮窗权限，并确认 Android 的屏幕共享请求。在 Android 14 及以上版本中，选择共享整个屏幕，以便在其他应用中翻译。
3. **打开游戏或应用，点击悬浮按钮。** 译文会显示在屏幕上。长按按钮打开菜单，可选择区域或切换翻译模式。

还可以输入或粘贴文字，从其他应用分享文字到 **Clickn**，或者翻译图库中的照片和截图。结果可复制、分享，文字翻译会保存在本地历史记录中。Google 无需密钥；下载支持的语言模型后，可使用 ML Kit 离线翻译。其他 API 服务使用你自己的凭据。

**[下载 APK](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/ClicknTranslate-1.8.2-arm64.apk)** · [Android 指南（英语）](../ANDROID.md) · [Android 源代码](https://github.com/jabrailkhalil/clickntranslate/tree/android)

## 桌面版：输入文字，获得翻译

支持区域 OCR、全屏翻译、其他应用中的选中文本翻译、译文替换，以及跟随多个区域变化的动态翻译。替换模式可先全选输入框。文档工作区支持并排编辑原文和译文。

## 选择引擎

在线翻译：Google、MyMemory、Lingva、LibreTranslate。离线翻译：下载模型后的 Argos Translate 和 Hy-MT。本地 OCR：Windows OCR、Apple Vision、Tesseract、RapidOCR、EasyOCR，具体取决于系统。

在 **Settings → Translation and OCR → Language packages → API** 中配置自己的 OpenAI、Gemini、Claude、DeepL、LibreTranslate 或 Custom API 密钥。对于支持图片的模型，可明确启用图片输入，由同一服务完成识别与翻译。

本地 OCR 在设备上处理图片。在线服务接收待翻译文本；启用的视觉 API 也会接收所选图片。服务商可能有独立的价格和限额。[隐私说明](../../PRIVACY.md)。

## 按你的习惯使用

十二种桌面界面语言，包括阿拉伯语及从右到左布局，包含提示与内置指南；浅色和深色主题；独立的界面缩放与结果字号；可自定义快捷键；设置导入导出；可选的本地历史记录。点击桌面伙伴即可使用操作菜单，也可以隐藏伙伴。

桌面包已包含 Python。Windows 和 Mac 使用 jabrailkhalil 自签名证书，可能出现 SmartScreen 提示；Mac 应用未经过 Apple 公证。[首次启动指南](../guides/setup.zh-CN.md)。在 Mac 上，为相关功能授予屏幕录制与辅助功能权限。[Linux 设置与快捷键](../LINUX.md)。

桌面 1.8.2 在应用内从 GitHub Releases 下载更新。Mac/Linux 1.8.1 及更早版本需要先手动安装本次升级；受保护的安装位置可能需要手动替换。Microsoft Store 版本通过商店更新。

Android 有独立的屏幕、文字、照片与历史界面：[移动版指南](https://github.com/jabrailkhalil/clickntranslate/tree/android#readme)。下载计数统计发布文件的下载次数，不是独立用户数。

[完整英文指南](../../README.md) · [反馈问题](https://github.com/jabrailkhalil/clickntranslate/issues) · [GPL-3.0](../../LICENSE)

## 更多演示

### 提取图片文字

![提取图片文字](../images/area-ocr-demo-v2.gif)

### 翻译选中文字

![翻译选中文字](../images/selected-text-demo-v2.gif)

### 翻译整个屏幕

![翻译整个屏幕](../images/fullscreen-translation-demo-v2.gif)

<sub>这些是桌面版工作流程的录像，当前窗口外观可能有所不同。</sub>
