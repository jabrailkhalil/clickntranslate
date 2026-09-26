<!-- Generated from docs/landing/tools/setup-content.mjs. -->
# Instalación y primer inicio

[English](setup.en.md) · [Русский](setup.ru.md) · **Español** · [Deutsch](setup.de.md) · [Français](setup.fr.md) · [中文](setup.zh-CN.md)

Configura Windows y Mac paso a paso.

Las versiones actuales usan la identidad autofirmada jabrailkhalil. No es un certificado de confianza pública de Windows ni un Apple Developer ID; la app de Mac no está notarizada. No necesitas instalar el certificado del autor ni firmar la app por tu cuenta.

[Descargas oficiales y sumas de comprobación](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

<a id="windows"></a>

## Windows: instalación, SmartScreen y Defender

### 1. Instala o extrae

Descarga desde este sitio o jabrailkhalil/clickntranslate en GitHub. Ejecuta el instalador o extrae todo el ZIP portable en una carpeta propia y abre ClicknTranslate.exe. Conserva la carpeta app a su lado. Python está incluido.

### 2. Si SmartScreen bloquea el inicio

Para el archivo oficial en el que confías, elige Más información → Ejecutar de todas formas en la advertencia de SmartScreen, si aparece esa opción. Esta advertencia de reputación es distinta de una detección del antivirus.

### 3. Si Defender puso un archivo en cuarentena

Abre Seguridad de Windows → Protección contra virus y amenazas → Historial de protección. Comprueba la ruta y el nombre de la amenaza, actualiza las definiciones y vuelve a analizar. Solo si verificaste el archivo oficial y estás seguro de que es un falso positivo, elige Restaurar. Si vuelve a detectarlo, abre el nuevo evento y elige Permitir en el dispositivo. Puede requerir autorización de administrador.

### 4. Si no puedes permitir la app

Smart App Control o una política de tu organización pueden impedir una excepción. Consulta al administrador o informa del bloqueo al proyecto. Mantén activo el antivirus; no excluyas Descargas, unidades completas ni todas las aplicaciones.

Una firma autofirmada o una suma coincidente no prueban que una alerta sea falsa. Comunica detecciones repetidas con la versión, nombre del archivo, SHA-256 y nombre exacto de la amenaza.

<a id="macos"></a>

## Mac: aprobar el inicio y los permisos

### 1. Elige tu versión e instala

Mira el chip o procesador en Apple → Acerca de este Mac. Elige Apple Silicon para M1 o posterior, o Intel para Mac Intel. Abre el DMG y arrastra ClicknTranslate.app a Aplicaciones. Ejecuta esa copia, no la del DMG.

### 2. Intenta abrirla una vez

Si macOS no puede verificar al desarrollador o comprobar la app, cierra el aviso con Aceptar o Cancelar. Ese intento permite que aparezca la opción de autorización en los ajustes.

### 3. Autoriza esta aplicación

Ve a Ajustes del Sistema → Privacidad y seguridad, baja hasta Seguridad y pulsa Abrir igualmente (Open Anyway) para ClicknTranslate. Autentícate si se solicita y confirma Abrir en el siguiente aviso. Autoriza solo la descarga oficial en la que confías.

### 4. Permite grabar la pantalla

Tras la bienvenida, pulsa Activar junto a Grabación de pantalla en el diálogo de configuración. En Privacidad y seguridad → Grabación de pantalla o Grabación de pantalla y audio del sistema, activa ClicknTranslate. Si hace falta, añade /Applications/ClicknTranslate.app con +; si no se ofrece esa opción, inicia una captura desde la app para solicitar acceso.

### 5. Permite accesibilidad

Pulsa Activar junto a Accesibilidad o abre Privacidad y seguridad → Accesibilidad. Activa la misma app instalada. Este permiso independiente permite copiar y reemplazar texto seleccionado en otras aplicaciones.

### 6. Reinicia y vuelve

Acepta Salir y volver a abrir si macOS lo ofrece. Si no, sal mediante el icono de la app en la barra de menús y ábrela desde Aplicaciones. Cerrar solo la ventana puede dejarla en ejecución. Pulsa Comprobar de nuevo → Continuar en el diálogo.

Tras actualizar puede quedar una copia antigua en la lista. Si el acceso sigue fallando, cierra la app, elimina únicamente su entrada antigua con − cuando esté disponible y añade con + la copia de Aplicaciones. Activa el permiso otra vez.

Si aparece que la app está dañada o dañará tu ordenador, vuelve a descargarla del lanzamiento oficial, compara la suma y comunica el mensaje exacto. No es una simple advertencia de desarrollador. Esta guía no requiere desactivar Gatekeeper, quitar la cuarentena en Terminal ni volver a firmar la app.

## Tu primera traducción

Elige los idiomas, pulsa la mascota → Traducir área y marca el texto. También puedes usar Ctrl + Alt + T en Windows o Command + Option + T en Mac. Activa la mascota en Ajustes si está oculta. La traducción en línea requiere internet; sin conexión, descarga antes los modelos de idiomas.

## Comprueba el archivo antes de permitirlo

Compara SHA-256 con el valor de ese archivo y versión en el archivo verification o .sha256 del lanzamiento oficial. La coincidencia comprueba integridad, no aprobación del antivirus. Sustituye la ruta de ejemplo por tu instalador o DMG.

Windows · PowerShell:

```powershell
Get-FileHash -LiteralPath "C:\path\to\installer.exe" -Algorithm SHA256
```

macOS · Terminal:

```sh
shasum -a 256 "/path/to/Click-n-Translate.dmg"
```

[Comunicar el bloqueo y el mensaje exacto](https://github.com/jabrailkhalil/clickntranslate/issues)

## Instrucciones de Apple y Microsoft

- [Abrir una app no verificada en Mac](https://support.apple.com/en-us/102445)
- [Grabación de pantalla en Mac](https://support.apple.com/guide/mac-help/mchld6aa7d23/mac)
- [Accesibilidad en Mac](https://support.apple.com/guide/mac-help/mh43185/mac)
- [Historial de protección de Windows](https://support.microsoft.com/en-us/windows/security/windows-security/protection-history-in-the-windows-security-app)
- [Reputación de Windows SmartScreen](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
