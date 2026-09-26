# Click'n'Translate

OCR y traducción de pantalla gratuitos y de código abierto para **Windows, Linux y macOS**. Extrae texto de aplicaciones, imágenes y juegos, traduce texto seleccionado o sigue los cambios en varias regiones de la pantalla.

[English](../../README.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · **Español** · [Français](README.fr.md)

![Tres formas de usar Click'n'Translate](../images/how-it-works.png)

## Descargar 1.8.1

| Sistema | Descarga | Uso |
| --- | --- | --- |
| Windows x64 | [Instalador (.exe)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-windows-x64-installer.exe) | Instalación normal en Windows 10/11, x64. |
| Windows x64 | [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-windows-portable-x64.zip) | Uso sin instalación; extrae todo el archivo. |
| Linux x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-linux-x86_64.AppImage) | Aplicación de un solo archivo para Linux x86_64; dale permiso de ejecución. |
| Mac — Apple Silicon | [DMG (M1+)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-macos-arm64.dmg) | Instalación en Apple Silicon (M1 o posterior), con macOS 13.4 o posterior. |
| Mac — Intel | [DMG (Intel)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.1/Click-n-Translate-1.8.1-macos-x86_64.dmg) | Instalación en Mac Intel (x86_64), con macOS 13.4 o posterior. |

[Todas las descargas, sumas SHA-256 y firmas](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.1).

Las versiones de Windows y macOS usan por ahora un **certificado autofirmado llamado `jabrailkhalil`**. Windows puede mostrar una advertencia de SmartScreen. La aplicación para Mac aún no tiene Developer ID de Apple ni notarización, por lo que Gatekeeper puede bloquear el primer inicio. Linux incluye firmas OpenPGP separadas. Elige **Apple Silicon** para chips M1 o posteriores, o **Intel** para Mac con procesador Intel.

**Primer inicio:** [Windows: SmartScreen y Defender](../guides/setup.es.md#windows) · [Mac: abrir la app y conceder permisos](../guides/setup.es.md#macos).

**Actualizaciones:** Windows se actualiza desde la aplicación. En macOS y Linux, descarga el nuevo DMG/AppImage y reemplaza la aplicación manualmente, conservando tus datos.

## Funciones

- OCR de pantalla, traducción de texto seleccionado, superposición a pantalla completa y traducción dinámica de varias regiones.
- Traducción en línea y OCR local; traducción sin conexión tras descargar los modelos de idiomas.
- Traducción de documentos, atajos configurables y asistente de escritorio.
- Temas claro y oscuro, seis idiomas de interfaz y preferencias de ventana independientes por modo.
- **1.8.0:** bienvenida unificada, menús de idiomas más claros, mejoras de superposición dinámica, guía de permisos en Mac y barras de desplazamiento finas.

El espacio de documentos abre `.txt`, `.md`, `.docx`, `.pdf`, `.html`, `.htm` y `.rtf`. Edita el original y la traducción en paralelo, u oculta el original para reducir la ventana. Ajustes incluye importación y exportación de preferencias e historiales locales opcionales.

## Míralo en acción

### Traducir texto de juegos

![Traducir texto de juegos](../images/translation-demo-v2.gif)

### Copiar texto de cualquier zona de la pantalla

![Copiar texto de cualquier zona de la pantalla](../images/area-ocr-demo-v2.gif)

### Traducir texto seleccionado en una aplicación

![Traducir texto seleccionado en una aplicación](../images/selected-text-demo-v2.gif)

### Traducir toda la pantalla

![Traducir toda la pantalla](../images/fullscreen-translation-demo-v2.gif)

### Actualizar con un clic (Windows)

![Actualizar con un clic (Windows)](../images/update-demo.gif)

## Mascota de escritorio

¿Prefieres hacer clic en lugar de memorizar atajos? Haz clic en la mascota para traducir un área o toda la pantalla, reconocer y copiar texto, abrir el traductor, iniciar la traducción dinámica o traducir un documento. Puedes ocultarla cuando no la necesites.

| Tema claro | Tema oscuro |
| --- | --- |
| ![Tema claro](../images/mascot-light.png) | ![Tema oscuro](../images/mascot-dark.png) |

## Traducción dinámica

Selecciona una o varias áreas de la pantalla y los idiomas. La traducción se actualiza cuando cambia el texto, sobre el original o en un área separada.

Ejemplo de configuración: el marco morado indica el área de lectura y el verde, un área separada para la traducción.

<img src="../images/dynamic-translation-regions.png" alt="Ejemplo de configuración: el marco morado indica el área de lectura y el verde, un área separada para la traducción." width="760">

## Atajos de teclado

| Atajo predeterminado | Acción |
| --- | --- |
| `Ctrl + Alt + C` | Extraer el texto de un área y copiarlo |
| `Ctrl + Alt + T` | Capturar un área, reconocer el texto y traducirlo |
| `Ctrl + Alt + F` | Traducir la pantalla completa |
| `Ctrl + Alt + Q` | Traducir el texto seleccionado en la aplicación activa |
| `Ctrl + Shift + Q` | Sustituir el texto seleccionado por su traducción |
| `Ctrl + Shift + Space` | Mostrar u ocultar Click'n'Translate |
| `Ctrl + Alt + G` | Iniciar o detener la traducción dinámica de las áreas elegidas |

Todos los atajos se pueden modificar o borrar en **Ajustes → Configurar atajos**. Las parejas de idiomas se recuerdan por separado para OCR, selección, sustitución, pantalla completa y traducción dinámica.

La tabla muestra los atajos de Windows. En **macOS**, usa **Command** en lugar de Ctrl y **Option** en lugar de Alt. En **Linux**, asigna los comandos en los ajustes de teclado del escritorio: [guía de Linux](../LINUX.md).

## Motores de traducción y OCR

| Tipo | Motores | Recomendado para |
| --- | --- | --- |
| Traducción en línea | Google, MyMemory, Lingva, LibreTranslate | Traducción rápida sin descargar un modelo |
| Traducción sin conexión | Argos Translate, Hy-MT | Traducción privada tras instalar los paquetes elegidos |
| OCR | Windows OCR / Apple Vision, Tesseract, RapidOCR, EasyOCR | Extraer texto de distintos alfabetos y tipos de imagen |

En **Ajustes → Paquetes de idiomas** puedes instalar y eliminar motores OCR, idiomas y modelos de traducción sin conexión. Solo se descargan los paquetes elegidos; los motores locales instalados funcionan sin internet. El OCR nativo es Windows OCR en Windows y Apple Vision en macOS. La disponibilidad de los traductores en línea depende del servicio.

## Primeros pasos

1. Descarga el archivo para tu sistema y abre la aplicación. Python ya está incluido.
2. Elige el motor OCR, el proveedor de traducción y los idiomas en Ajustes. Descarga modelos para traducir sin conexión.
3. Elige una acción de captura o traducción. En Mac, sigue las indicaciones para conceder permisos de **grabación de pantalla** y **accesibilidad**. En Linux, configura los atajos del escritorio con la [guía de Linux](../LINUX.md).

El OCR se ejecuta localmente. La traducción en línea envía el texto al proveedor elegido; usa un motor sin conexión para traducir localmente. Consulta [Privacidad](../../PRIVACY.md).

## Ayuda y desarrollo

[Linux](../LINUX.md) · [macOS y compilación](../MACOS.md) · [Informar de un problema](https://github.com/jabrailkhalil/clickntranslate/issues) · [Licencia GPL-3.0](../../LICENSE)

Para un diagnóstico, abre **Ayuda → Informe de errores** y adjunta el ZIP generado al problema. No incluye texto del portapapeles, contenido de documentos, historiales ni credenciales.

Click’n’Translate es gratuito. Si te resulta útil, agradecemos que [des una estrella al proyecto en GitHub](https://github.com/jabrailkhalil/clickntranslate) y [te unas a Telegram](https://t.me/jabrail_digital).
