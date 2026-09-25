# Click'n'Translate

适用于 **Windows、Linux 和 macOS** 的免费开源屏幕 OCR 与翻译工具。从应用、图片和游戏中提取文字，翻译选中文本，或持续翻译一个或多个屏幕区域。

[English](../../README.md) · [Русский](README.ru.md) · **简体中文** · [Español](README.es.md) · [Français](README.fr.md)

## 下载 1.8.0

| 系统 | 下载 | 用途 |
| --- | --- | --- |
| Windows x64 | [安装程序 (.exe)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-x64-installer.exe) | 在 Windows 10/11 x64 上正常安装。 |
| Windows x64 | [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-portable-x64.zip) | 无需安装；请完整解压后运行。 |
| Linux x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.AppImage) | Linux x86_64 单文件应用；启动前请赋予执行权限。 |
| Linux x86_64 | [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.tar.gz) | Linux x86_64 应用文件夹；解压后运行。 |
| macOS arm64 | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.dmg) | 适用于 Apple Silicon（M1 及更新芯片），要求 macOS 13.4 或更新版本。 |
| macOS arm64 | [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.zip) | 同一 Apple Silicon 应用的 ZIP 压缩包。 |

[全部下载、SHA-256 校验和及签名文件](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.0).

Windows 和 macOS 版本目前使用名为 **`jabrailkhalil` 的自签名证书**。Windows 可能显示 SmartScreen 警告；Mac 版本尚无 Apple Developer ID 签名或公证，Gatekeeper 可能阻止首次启动。Linux 下载提供独立的 OpenPGP 签名。本次发行不包含 Intel Mac 版本。

## 功能

- 屏幕 OCR、选中文本翻译、全屏叠加和多区域动态翻译。
- 在线翻译与本地 OCR；下载语言模型后可使用离线翻译。
- 文档翻译、可配置快捷键和桌面助手。
- 明暗主题、六种界面语言，以及每种模式独立的窗口偏好设置。
- **1.8.0：**统一欢迎界面、改进语言菜单和动态叠加、macOS 权限引导，以及全应用细滚动条。

## 开始使用

1. 下载适合您系统的文件并打开应用。发行包已包含 Python 运行环境。
2. 在设置中选择 OCR 引擎、翻译服务及语言。离线翻译需先下载语言模型。
3. 选择捕获或翻译操作。在 Mac 上按照提示授予**屏幕录制**和**辅助功能**权限。Linux 桌面快捷键设置请参阅 [Linux 指南](../../docs/LINUX.md)。

OCR 在本地运行。在线翻译会将文本发送给您选择的服务；如需本地翻译，请使用离线引擎。参阅[隐私说明](../../PRIVACY.md)。

## 帮助与开发

[Linux 指南](../../docs/LINUX.md) · [macOS 指南与构建](../../docs/MACOS.md) · [反馈问题](https://github.com/jabrailkhalil/clickntranslate/issues) · [GPL-3.0 许可证](../../LICENSE)

Click’n’Translate 完全免费。如果对您有帮助，欢迎[在 GitHub 上为项目加星](https://github.com/jabrailkhalil/clickntranslate)，并[加入 Telegram](https://t.me/jabrail_digital)。
