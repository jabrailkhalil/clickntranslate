# Click'n'Translate

OCR y traducción de pantalla gratuitos y de código abierto para **Windows, Linux y macOS**. Extrae texto de aplicaciones, imágenes y juegos, traduce texto seleccionado o sigue los cambios en varias regiones de la pantalla.

[English](../../README.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · **Español** · [Français](README.fr.md)

## Descargar 1.8.0

| Sistema | Descarga | Uso |
| --- | --- | --- |
| Windows x64 | [Instalador (.exe)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-x64-installer.exe) | Instalación normal en Windows 10/11, x64. |
| Windows x64 | [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-portable-x64.zip) | Uso sin instalación; extrae todo el archivo. |
| Linux x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.AppImage) | Aplicación de un solo archivo para Linux x86_64; dale permiso de ejecución. |
| Linux x86_64 | [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.tar.gz) | Carpeta de la aplicación para Linux x86_64; extrae antes de ejecutar. |
| macOS arm64 | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.dmg) | Instalación en Apple Silicon (M1 o posterior), con macOS 13.4 o posterior. |
| macOS arm64 | [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.zip) | La misma aplicación para Apple Silicon en un archivo ZIP. |

[Todas las descargas, sumas SHA-256 y firmas](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.0).

Las versiones de Windows y macOS usan por ahora un **certificado autofirmado llamado `jabrailkhalil`**. Windows puede mostrar una advertencia de SmartScreen. La aplicación para Mac aún no tiene Developer ID de Apple ni notarización, por lo que Gatekeeper puede bloquear el primer inicio. Linux incluye firmas OpenPGP separadas. Esta versión no incluye una compilación para Mac Intel.

## Funciones

- OCR de pantalla, traducción de texto seleccionado, superposición a pantalla completa y traducción dinámica de varias regiones.
- Traducción en línea y OCR local; traducción sin conexión tras descargar los modelos de idiomas.
- Traducción de documentos, atajos configurables y asistente de escritorio.
- Temas claro y oscuro, seis idiomas de interfaz y preferencias de ventana independientes por modo.
- **1.8.0:** bienvenida unificada, menús de idiomas más claros, mejoras de superposición dinámica, guía de permisos en Mac y barras de desplazamiento finas.

## Primeros pasos

1. Descarga el archivo para tu sistema y abre la aplicación. Python ya está incluido.
2. Elige el motor OCR, el proveedor de traducción y los idiomas en Ajustes. Descarga modelos para traducir sin conexión.
3. Elige una acción de captura o traducción. En Mac, sigue las indicaciones para conceder permisos de **grabación de pantalla** y **accesibilidad**. En Linux, configura los atajos del escritorio con la [guía de Linux](../../docs/LINUX.md).

El OCR se ejecuta localmente. La traducción en línea envía el texto al proveedor elegido; usa un motor sin conexión para traducir localmente. Consulta [Privacidad](../../PRIVACY.md).

## Ayuda y desarrollo

[Linux](../../docs/LINUX.md) · [macOS y compilación](../../docs/MACOS.md) · [Informar de un problema](https://github.com/jabrailkhalil/clickntranslate/issues) · [Licencia GPL-3.0](../../LICENSE)

Click’n’Translate es gratuito. Si te resulta útil, agradecemos que [des una estrella al proyecto en GitHub](https://github.com/jabrailkhalil/clickntranslate) y [te unas a Telegram](https://t.me/jabrail_digital).
