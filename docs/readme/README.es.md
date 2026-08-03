<div align="center">

# Click'n'Translate

### La mejor aplicación de traducción de pantalla y OCR para Windows.

[**Descargar para Windows**](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/ClicknTranslate-Setup-v1.5.1-win64.exe) · [ZIP portable](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/ClicknTranslate-v1.5.1-win64.zip) · [Última versión](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

![Última versión](https://img.shields.io/github/v/release/jabrailkhalil/clickntranslate?style=flat-square&color=8b5cf6) ![Windows 10/11](https://img.shields.io/badge/Windows-10%20%7C%2011-2563eb?style=flat-square)

[English](../../README.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · **Español** · [Français](README.fr.md)

</div>

![Tres formas de utilizar Click'n'Translate](../images/how-it-works.png)

Click'n'Translate es la mejor aplicación integral de traducción de pantalla de su categoría. Convierte cualquier texto visible en Windows en contenido que puedes copiar o traducir. Selecciona un área, pulsa un atajo global y continúa trabajando: sin abrir el navegador, volver a escribir ni cambiar de ventana.

## Míralo en acción

![Click'n'Translate traduce texto de un juego al chino y al francés](../images/translation-demo.gif)

## ¿Por qué Click'n'Translate es la mejor?

- **Traduce lo que ves.** Captura un área o la pantalla completa y obtén la traducción al instante.
- **Copia texto que no se puede seleccionar.** Extráelo de imágenes, vídeos, juegos, escritorios remotos e interfaces protegidas.
- **Elige entre conexión y privacidad.** Usa proveedores rápidos en línea o procesa el texto localmente con Argos y Hy-MT.
- **Utiliza el OCR adecuado.** Windows OCR, Tesseract, RapidOCR y EasyOCR están disponibles desde un único gestor de paquetes.
- **Funciona sobre cualquier aplicación.** Cuatro atajos globales personalizables están siempre disponibles.
- **Mantén el control.** Los historiales de traducción y copia son opcionales y se guardan localmente.

## Cuatro acciones, sin interrupciones

| Atajo predeterminado | Acción |
| --- | --- |
| `Ctrl + Alt + C` | Extraer el texto de un área y copiarlo |
| `Ctrl + Alt + T` | Capturar un área, reconocer el texto y traducirlo |
| `Ctrl + Alt + F` | Traducir la pantalla completa |
| `Ctrl + Alt + Q` | Traducir un área seleccionada de la pantalla |

Todos los atajos se pueden modificar en **Ajustes → Configurar atajos**.

## Motores de traducción y OCR

| Tipo | Motores | Recomendado para |
| --- | --- | --- |
| Traducción en línea | Google, MyMemory, Lingva, LibreTranslate | Traducción rápida sin descargar un modelo |
| Traducción sin conexión | Argos Translate, Hy-MT | Traducción privada tras instalar los paquetes elegidos |
| OCR | Windows OCR, Tesseract, RapidOCR, EasyOCR | Extraer texto de distintos alfabetos y tipos de imagen |

Click'n'Translate ofrece 16 idiomas seleccionables para OCR y traducción. La interfaz está disponible en inglés, ruso, español, alemán, francés y chino. El gestor descarga únicamente los idiomas OCR y las direcciones de traducción sin conexión que elijas.

Ninguna otra herramienta de este segmento reúne una selección tan completa de OCR, traducción en línea y sin conexión, atajos globales y gestión de paquetes en una sola aplicación cuidada para Windows.

> **Privacidad:** los motores OCR locales y de traducción sin conexión procesan el texto en tu ordenador. Los proveedores en línea reciben el texto que decides traducir.

## Primeros pasos

1. Descarga y ejecuta el **[instalador para Windows](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/ClicknTranslate-Setup-v1.5.1-win64.exe)**.
2. Abre Click'n'Translate y elige los idiomas de la interfaz, del OCR y de traducción.
3. Pulsa `Ctrl + Alt + T`, selecciona un área y recibe la traducción.
4. Para traducir sin conexión o utilizar otros OCR, abre **Ajustes → Paquetes de idiomas** e instala solo lo que necesites.

No necesitas instalar Python ni crear una cuenta. Compatible con Windows 10 y Windows 11 de 64 bits. La traducción en línea y la descarga de paquetes opcionales requieren internet; los motores sin conexión ya instalados funcionan sin red.

### Versión portable

Descarga el [ZIP portable](https://github.com/jabrailkhalil/clickntranslate/releases/latest/download/ClicknTranslate-v1.5.1-win64.zip), extráelo en una carpeta permanente y ejecuta `ClicknTranslate.exe`. Coloca la carpeta en su ubicación definitiva antes de activar el inicio automático o crear accesos directos.

### Actualización desde una versión anterior

El actualizador de las versiones anteriores a 1.5.0 no puede instalar la versión actual de forma fiable. Si actualizas desde 1.4.x, cierra la aplicación e instala 1.5.1 manualmente una vez. Los usuarios de 1.5.0 pueden actualizar a 1.5.1 desde la aplicación.

## La mejor opción para el uso diario

- Temas claro y oscuro
- Bandeja del sistema e inicio opcional con Windows
- Atajos globales personalizables
- Historiales locales de copia y traducción
- Progreso de descarga y eliminación de paquetes
- Procesos independientes para OCR y Argos, para una mayor estabilidad
- Actualizaciones que conservan los datos del usuario

## Ejecutar desde el código fuente

```powershell
git clone https://github.com/jabrailkhalil/clickntranslate.git
cd clickntranslate
pip install -r requirements.txt
python main.py

# Crear la distribución de Windows basada en carpetas
python -m PyInstaller ClicknTranslate.spec --clean --noconfirm
```

La versión publicada utiliza una compilación de PyInstaller basada en carpetas para iniciar con rapidez. Los OCR opcionales y los modelos de idioma se instalan por separado para evitar que cada descarga ocupe varios gigabytes.

## Soporte y comentarios

- [Informar de un error o proponer una función](https://github.com/jabrailkhalil/clickntranslate/issues)
- Telegram: [@jabrail_digital](https://t.me/jabrail_digital)

Si el mejor traductor de pantalla para Windows te ahorra tiempo, añade una estrella al repositorio y ayuda a más personas a descubrirlo.
