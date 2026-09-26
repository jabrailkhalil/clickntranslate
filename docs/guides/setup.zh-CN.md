<!-- Generated from docs/landing/tools/setup-content.mjs. -->
# 安装与首次启动

[English](setup.en.md) · [Русский](setup.ru.md) · [Español](setup.es.md) · [Deutsch](setup.de.md) · [Français](setup.fr.md) · **中文**

按步骤设置 Windows 和 Mac。

当前版本使用 jabrailkhalil 自签名身份。它不是 Windows 公开信任的证书，也不是 Apple Developer ID；Mac 应用尚未经过 Apple 公证。你不需要安装作者的证书，也不需要自行给应用签名。

[官方下载与校验和](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

<a id="windows"></a>

## Windows：安装、SmartScreen 与 Defender

### 1. 安装或完整解压

从本网站或 GitHub 的 jabrailkhalil/clickntranslate 下载。运行安装程序，或将 Portable ZIP 完整解压到单独文件夹后打开 ClicknTranslate.exe。保留旁边的 app 文件夹。已包含 Python。

### 2. SmartScreen 阻止启动时

确认是你信任的官方文件后，在“Windows 已保护你的电脑”提示中选择“更多信息”→“仍要运行”（如果提供）。信誉警告与杀毒软件检测到威胁是两回事。

### 3. Defender 隔离了文件时

打开“Windows 安全中心”→“病毒和威胁防护”→“保护历史记录”。核对文件路径和威胁名称，更新安全情报后重新扫描。只有验证了官方文件并确信是误报时，才选择“还原”。如果再次检测到它，打开新的记录并选择“允许在设备上”。可能需要管理员授权。

### 4. 无法允许应用时

智能应用控制或组织策略可能不允许例外。联系管理员或向项目报告阻止信息。保持杀毒防护开启，不要排除整个“下载”文件夹、磁盘或所有应用。

自签名证书或相同校验和不能证明威胁检测是误报。请提供应用版本、文件名、SHA-256 和准确的威胁名称，以便调查反复出现的检测。

<a id="macos"></a>

## Mac：允许启动并授予权限

### 1. 选择版本并安装

在 Apple 菜单→“关于本机”中查看芯片或处理器。M1 及更新芯片选择 Apple Silicon，Intel Mac 选择 Intel。打开 DMG，将 ClicknTranslate.app 拖入“应用程序”。启动安装后的副本，不要运行 DMG 内的副本。

### 2. 先尝试打开一次

如果 macOS 提示无法验证开发者或 Apple 无法检查应用，请点“完成”或“取消”关闭提示。尝试打开后，设置中才会出现允许打开的选项。

### 3. 允许此应用启动

打开“系统设置”→“隐私与安全性”，向下滚动至“安全性”，为 ClicknTranslate 选择“仍要打开”（Open Anyway）。按提示验证身份，并在下一次提示中点“打开”。只允许你信任的官方下载文件。

### 4. 允许屏幕录制

欢迎窗口之后，在 Mac 设置对话框中点击“屏幕录制”旁的“启用”。在“隐私与安全性”→“屏幕录制”或“屏幕与系统音频录制”中启用 ClicknTranslate，以便 OCR 读取屏幕。必要时用 + 添加 /Applications/ClicknTranslate.app；如果无法手动添加，在应用中启动屏幕捕获以请求权限。

### 5. 允许辅助功能

点击“辅助功能”旁的“启用”，或进入“隐私与安全性”→“辅助功能”。启用同一个已安装的应用，以便复制、替换其他应用中的选中文本。这与屏幕录制是两个独立权限。

### 6. 重启并返回

如果 macOS 提示“退出并重新打开”，请确认。否则从菜单栏中的应用图标选择退出，再从“应用程序”打开。只关闭窗口可能不会退出应用。回到设置对话框，点击“重新检查”→“继续”。

升级后权限列表可能仍有旧副本。若权限仍无效，退出应用，仅用 − 移除它的旧条目（如可用），再用 + 添加“应用程序”中的副本并启用。不要修改其他应用的权限。

如果提示应用已损坏或将损坏电脑，不要当作普通开发者警告忽略。重新从官方发布页下载、核对校验和并报告完整提示。本指南不需要禁用 Gatekeeper、通过终端移除隔离属性或重新签名。

## 开始第一次翻译

选择源语言和目标语言，点击吉祥物→翻译区域，再框选文字。也可使用 Windows 的 Ctrl + Alt + T 或 Mac 的 Command + Option + T。如果吉祥物隐藏了，可在设置中启用。在线翻译需要网络，离线翻译需要事先下载语言模型。

## 允许之前核对文件

将下载文件的 SHA-256 与官方发布的 verification 压缩包或 .sha256 文件中相同版本、相同文件的值比较。匹配仅确认完整性，不代表杀毒软件认可。请将示例路径替换为你的安装程序或 DMG 路径。

Windows · PowerShell:

```powershell
Get-FileHash -LiteralPath "C:\path\to\installer.exe" -Algorithm SHA256
```

macOS · Terminal:

```sh
shasum -a 256 "/path/to/Click-n-Translate.dmg"
```

[仍被阻止？报告完整提示](https://github.com/jabrailkhalil/clickntranslate/issues)

## Apple 与 Microsoft 说明

- [打开未经验证的 Mac 应用](https://support.apple.com/en-us/102445)
- [Mac 屏幕录制权限](https://support.apple.com/guide/mac-help/mchld6aa7d23/mac)
- [Mac 辅助功能权限](https://support.apple.com/guide/mac-help/mh43185/mac)
- [Windows 保护历史记录](https://support.microsoft.com/en-us/windows/security/windows-security/protection-history-in-the-windows-security-app)
- [Windows SmartScreen 信誉](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
