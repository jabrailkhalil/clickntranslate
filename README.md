# Click'n'Translate

![Click'n'Translate Logo](icons/icon.ico)

**Click'n'Translate** is a powerful, lightweight desktop application for instant screen translation and text extraction (OCR). Capture any text on your screen, translate it instantly, or copy it to clipboard — all with simple hotkeys.

## 📥 Download

**[Download Latest Release](https://github.com/jabrailkhalil/clickntranslate/releases)**

> The application is **fully portable** — no registry entries, no system modifications. It cleans up its own cache (button available in Settings).

## 🛠 Installation

1. **Download** the latest release from [Releases](https://github.com/jabrailkhalil/clickntranslate/releases)
2. **Extract** the archive to your preferred location (e.g., `C:\Programs\ClicknTranslate`)
3. **Run** `ClicknTranslate.exe`
4. **(Optional)** Enable "Start with Windows" in Settings for auto-start
5. **(Optional)** Run `CreateShortcut.bat` to create a desktop shortcut

> ⚠️ **Important**: Move the folder to its permanent location *before* enabling auto-start or creating shortcuts. Moving the folder later will break these features.

> **Updating from 1.4.5:** that version contains a broken updater and requires one manual update. Close the app, extract 1.4.6 into a new folder, and copy the old `data` folder into it. Automatic updates after 1.4.6 use the corrected transactional updater.

## 🚀 Features

### 📷 Advanced OCR (Optical Character Recognition)
- **Instant Text Capture**: Select any area on your screen to extract text instantly
- **Four OCR Engines**: Choose **Windows OCR**, **Tesseract**, **RapidOCR**, or **EasyOCR**; optional portable engines can be installed and removed from Settings
- **Universal Mode (AUTO)**: Compares available Windows OCR languages and image variants to select the most reliable result
- **Language packages**: Open **Settings → Language packages** to install Windows OCR capabilities, Tesseract/EasyOCR language data, the shared RapidOCR model, and Argos translation directions before first use

### 🌐 Instant Translation
- **Multiple Translation Engines**:
  - **Google Translate** — fast and accurate (recommended)
  - **Argos Translate** — fully offline, private
  - **MyMemory** — free API (5000 chars/day limit)
  - **Lingva** — Google proxy via public servers
  - **LibreTranslate** — open source
- **Offline engine setup**: Argos directions can be installed or removed in **Settings → Language packages** with visible download progress; Hy-MT is installed separately from Settings.
- **Visual Direction**: Clear indication of translation direction (RU → EN, EN → RU)
- **History Tracking**: Built-in history viewer saves all translations locally

### ⚡ Productivity & Workflow
- **Global Hotkeys**:
  - **`Ctrl + Alt + C`**: Quick Copy Mode — OCR & copy to clipboard
  - **`Ctrl + Alt + T`**: Quick Translate Mode — OCR & translate
- **Photoshop-style Overlay**: Professional selection interface with glow effects
- **Smart Clipboard**: Automatically copies recognized/translated text
- **Separate Histories**: Maintains copy history and translation history

### 🎨 Modern UI & Customization
- **Dark & Light Themes**: Fully distinct themes
- **System Tray Integration**: Minimizes to tray for clean taskbar
- **Bilingual Interface**: Russian and English UI
- **Cache Management**: Clear cache button in Settings
- **Responsive Design**: Polished layout with smooth interactions

## 🎮 How to Use

1. **Launch the App**: Main window provides access to all settings
2. **Configure Settings**:
   - Select your OCR Engine (Windows recommended)
   - Set your Interface Language and Target Translation Language
   - Customize Hotkeys if desired
3. **Copy Text** (`Ctrl + Alt + C`):
   - Select **AUTO** for numbers/Latin, or specific language for better accuracy
   - Click and drag to select text area
   - Text is copied to clipboard
4. **Translate Text** (`Ctrl + Alt + T`):
   - Select source language (RU → EN or EN → RU)
   - Click and drag to select text area
   - Translation appears in popup and copies to clipboard

## 💡 Tips

- **AUTO mode** works best for numbers, dates, and Latin text
- **RU mode** works best for Cyrillic text
- **Right-click** during selection to exit the app
- **ESC** to cancel current selection
- Windows OCR requires its Windows capability for each language; install it from **Settings → Language packages → Windows**
- RapidOCR uses one shared Chinese/English recognition model rather than separate per-language packs

## 📦 Building from Source

```bash
# Clone repository
git clone https://github.com/jabrailkhalil/clickntranslate.git
cd clickntranslate

# Install dependencies
pip install -r requirements.txt

# Run application
python main.py

# Build executable
python -m PyInstaller ClicknTranslate.spec --clean --noconfirm
```

This generates a portable executable in the `dist` folder.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📬 Contact

- **Telegram**: [@jabrail_digital](https://t.me/jabrail_digital)
