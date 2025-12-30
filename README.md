# Click 'n Translate

![Click 'n Translate Logo](icons/icon.ico)

**Click 'n Translate** is a powerful, lightweight desktop application designed to make screen translation and text extraction (OCR) seamless and effortless. With a modern, user-friendly interface and robust features, it bridges the gap between seeing text on your screen and understanding it.

## 🚀 Features

### 📷 Advanced OCR (Optical Character Recognition)
- **Instant Text Capture**: Select any area on your screen to extract text instantly.
- **Multi-Engine Support**: Choose between **Windows OCR** (native, fast), **Tesseract**, or **RapidOCR** for optimal accuracy.
- **Language Support**: Seamlessly switch between **Russian** (ru) and **English** (en) recognition.

### 🌐 Instant Translation
- **Automatic Translation**: Recognized text is immediately translated to your preferred language.
- **Google Translate Integration**: Reliable and accurate translations powered by Google API.
- **History Tracking**: Never lose a translation. The built-in history viewer saves your translation sessions locally.

### ⚡ Productivity & Workflow
- **Global Hotkeys**:
  - **`Ctrl + Alt + C`**: Quick Copy Mode (OCR & Copy to Clipboard).
  - **`Ctrl + Alt + T`**: Quick Translate Mode (OCR & Translate).
- **Overlay Mode**: A non-intrusive, stay-on-top overlay allows you to select text without leaving your current window.
- **Clipboard Management**: Automatically copies recognized text to your clipboard.
- **Copy History**: Maintains a separate history of all text copied via the tool.

### 🎨 Modern UI & Customization
- **Dark & Light Themes**: Fully distinct themes to match your system preference or mood.
- **System Tray Integration**: Minimized to tray to keep your taskbar clean.
- **Smart Settings**: Configure behavior such as "Start Minimized", "Keep Visible on OCR", and more.
- **Responsive Design**: Polished layout with rounded corners and smooth interactions.

## 🛠 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jabrailkhalil/clickntranslate.git
   cd clickntranslate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure you have Python 3.8+ installed)*

3. **Run the application**:
   ```bash
   python main.py
   ```

## 📦 Building form Source

To create a standalone executable (`.exe`):

```bash
python build.py
```
This will generate a portable executable in the `dist` folder.

## 🎮 How to Use

1. **Launch the App**: The main window provides access to all settings.
2. **Settings**:
   - Select your OCR Engine (Windows recommended for Windows 10/11).
   - Set your **Interface Language** and **Target Translation Language**.
   - Customize Hotkeys if desired.
3. **Capture**:
   - Press **`Ctrl + Alt + T`**.
   - Your screen will dim slightly (optional).
   - Click and drag to select the text you want to translate.
   - The result will appear in a popup dialog.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---
*Developed by Jabrail (jabrailkhalil)*
