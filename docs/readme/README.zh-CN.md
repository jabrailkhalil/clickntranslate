<div align="center">

# Click'n'Translate

### Windows 上最好的屏幕翻译和 OCR 应用。

[**下载 Windows 版**](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/Click-n-Translate-1.5.3-windows-x64-installer.exe) · [便携版 ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/Click-n-Translate-1.5.3-windows-portable-x64.zip) · [最新版本](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

![最新版本](https://img.shields.io/github/v/release/jabrailkhalil/clickntranslate?style=flat-square&color=8b5cf6) ![Windows 10/11](https://img.shields.io/badge/Windows-10%20%7C%2011-2563eb?style=flat-square)

[English](../../README.md) · [Русский](README.ru.md) · **简体中文** · [Español](README.es.md) · [Français](README.fr.md)

</div>

![Click'n'Translate 的三种使用方式](../images/how-it-works.png)

Click'n'Translate 是同类产品中最好的全能屏幕翻译应用。它可将 Windows 屏幕上的任何内容转换为可复制或可翻译的文字。选择一个区域，按下全局快捷键，然后继续工作——无需打开浏览器、手动输入或频繁切换窗口。

## 实际演示

![Click'n'Translate 将游戏文字翻译成中文和法语](../images/translation-demo.gif)

## 为什么 Click'n'Translate 是最佳选择？

- **翻译屏幕上看到的内容。** 捕获指定区域或整个屏幕，并立即进行翻译。
- **复制无法选中的文字。** 从图片、视频、游戏、远程桌面和受保护的界面中提取文字。
- **在线与离线自由选择。** 使用快速在线服务，或通过 Argos 和 Hy-MT 在本机处理文字。
- **灵活选择 OCR 引擎。** 在同一个软件包管理器中使用 Windows OCR、Tesseract、RapidOCR 和 EasyOCR。
- **在任何应用中使用。** 四个可自定义的全局快捷键随时可用。
- **掌控自己的数据。** 翻译和复制历史记录可选启用，并保存在本机。

## 四个快捷操作

| 默认快捷键 | 操作 |
| --- | --- |
| `Ctrl + Alt + C` | 识别选定区域中的文字并复制 |
| `Ctrl + Alt + T` | 捕获区域、识别文字并翻译 |
| `Ctrl + Alt + F` | 翻译整个屏幕 |
| `Ctrl + Alt + Q` | 翻译选定的屏幕区域 |

所有快捷键均可在 **设置 → 配置快捷键** 中修改。

## 翻译与 OCR 引擎

| 类型 | 引擎 | 适用场景 |
| --- | --- | --- |
| 在线翻译 | Google、MyMemory、Lingva、LibreTranslate | 无需下载模型的快速翻译 |
| 离线翻译 | Argos Translate、Hy-MT | 安装所选软件包后的本地私密翻译 |
| OCR | Windows OCR、Tesseract、RapidOCR、EasyOCR | 识别不同文字系统和图像样式 |

Click'n'Translate 提供 16 种可选的 OCR 与翻译语言，界面支持英语、俄语、西班牙语、德语、法语和中文。软件包管理器只会下载您选择的 OCR 语言和离线翻译方向。

在同类 Windows 应用中，没有其他工具能像 Click'n'Translate 一样，将多种 OCR、在线与离线翻译、全局快捷键和完善的软件包管理如此出色地整合在一起。

> **隐私说明：**本地 OCR 和离线翻译引擎在您的电脑上处理文字。在线翻译服务会接收您主动提交翻译的文字。

## 快速开始

1. 下载并运行 **[Windows 安装程序](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/Click-n-Translate-1.5.3-windows-x64-installer.exe)**。
2. 启动 Click'n'Translate，选择界面语言、OCR 语言和翻译语言。
3. 按下 `Ctrl + Alt + T`，选择一个区域，即可获得翻译。
4. 如需离线翻译或其他 OCR 引擎，请打开 **设置 → 语言包**，只安装需要的组件。

无需安装 Python，也无需注册账户。支持 64 位 Windows 10 和 Windows 11。在线翻译和下载可选软件包需要网络连接；已安装的离线引擎无需联网即可工作。

### 便携版

下载[便携版 ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/Click-n-Translate-1.5.3-windows-portable-x64.zip)，将其解压到固定文件夹，然后运行 `ClicknTranslate.exe`。请在启用开机启动或创建快捷方式之前确定最终存放位置。

### 从旧版本升级

1.5.0 之前版本的更新程序无法可靠地安装当前版本。如果从 1.4.x 升级，请关闭旧应用并手动安装一次 1.5.3。1.5.0 及更高版本的用户可以直接在应用内更新到 1.5.3。

## 日常使用的最佳选择

- 深色与浅色主题
- 系统托盘和可选的 Windows 开机启动
- 可自定义全局快捷键
- 本地复制与翻译历史记录
- 下载进度和软件包卸载控制
- 独立 OCR 与 Argos 工作进程，提高稳定性
- 更新时保留用户数据

## 从源代码运行

```powershell
git clone https://github.com/jabrailkhalil/clickntranslate.git
cd clickntranslate
pip install -r requirements.txt
python main.py

# 构建文件夹形式的 Windows 发行版
python -m PyInstaller ClicknTranslate.spec --clean --noconfirm
```

正式版使用文件夹形式的 PyInstaller 构建，以获得更快的启动速度。可选 OCR 运行库和语言模型单独安装，避免让每次下载都达到数 GB。

## 支持与反馈

- [报告问题或提出功能建议](https://github.com/jabrailkhalil/clickntranslate/issues)
- Telegram：[@jabrail_digital](https://t.me/jabrail_digital)

如果这款最好的 Windows 屏幕翻译工具为您节省了时间，欢迎为仓库点亮 Star，帮助更多人发现它。
