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
  <a href="README.zh-CN.md">简体中文</a> ·
  <strong>Português</strong> ·
  <a href="README.it.md">Italiano</a>
</p>

<p align="center"><strong>Leia o texto da tela no seu idioma.</strong></p>
<p align="center">Windows · macOS · Linux · <a href="#android">Android</a></p>

<p align="center">
  <a href="https://github.com/jabrailkhalil/clickntranslate/releases/latest"><img src="https://img.shields.io/github/v/release/jabrailkhalil/clickntranslate?style=flat&amp;label=release&amp;color=73529a" alt="Latest release"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/jabrailkhalil/clickntranslate/releases"><img src="https://img.shields.io/github/downloads/jabrailkhalil/clickntranslate/total?style=flat&amp;label=downloads&amp;color=73529a" alt="GitHub release downloads"></a>
</p>

<p align="center">
  <strong><a href="#download">Baixar</a></strong>
  &nbsp;&nbsp;&nbsp;
  <a href="https://translate.clickn.dev/en/">Site</a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://t.me/jabrail_digital">Telegram</a>
</p>

Traduza jogos, copie texto de imagens, leia documentos e substitua mensagens pela tradução. Aplicativo gratuito e de código aberto para **Windows, macOS e Linux**, com uma edição própria para **Android**.

<p align="center">
  <img src="../../docs/images/translation-demo-v2.gif" alt="Leia o texto da tela no seu idioma." width="640">
</p>

<a name="download"></a>

## Baixar 1.8.2

| Sistema | Instalar | Portátil |
| --- | --- | --- |
| **Windows** 10/11 · x64 | [EXE](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-x64-installer.exe) | [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-portable-x64.zip) |
| **macOS** 13.4+ · Apple Silicon (M1+) | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-arm64.dmg) | — |
| **macOS** 13.4+ · Intel | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-x86_64.dmg) | — |
| **Linux** · x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.AppImage) | [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.tar.gz) |
| **Android** 8.0+ · ARM64 | [APK](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/ClicknTranslate-1.8.2-arm64.apk) | — |

[Todos os downloads](https://github.com/jabrailkhalil/clickntranslate/releases/latest)

<a name="android"></a>

## No Android: traduza sem sair do aplicativo

**Um botão flutuante para jogos e aplicativos, além de tradução de texto e fotos.** Funciona no celular, sem computador nem acesso root.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../images/android-home-dark-1.8.2.png">
    <img src="../images/android-home-light-1.8.2.png" alt="Tela inicial do Android com idiomas e ações de tradução de tela, imagens e texto" width="280">
  </picture>
</p>

<p align="center"><sub>Interface do Android 1.8.2 em russo. A versão Android tem seis idiomas de interface; português está disponível na versão desktop.</sub></p>

1. **Instale o APK** em um aparelho Android 8.0+ ARM64. Escolha o idioma da interface, o tema e os idiomas de tradução.
2. **Inicie a tradução da tela.** Permita a exibição sobre outros aplicativos e confirme a captura. No Android 14 ou superior, compartilhe a tela inteira para traduzir em outros aplicativos.
3. **Abra seu jogo ou aplicativo e toque no botão flutuante.** A tradução aparece sobre a tela. Mantenha o botão pressionado para escolher uma região ou outro modo no menu.

Você também pode digitar ou colar texto, compartilhá-lo com o **Clickn** de outro aplicativo e traduzir fotos ou capturas da galeria. Copie ou compartilhe os resultados e consulte o histórico local de textos. O Google funciona sem chave; o ML Kit permite traduzir offline após baixar os modelos dos idiomas compatíveis. Serviços de API adicionais usam suas próprias credenciais.

[Guia Android (inglês)](../ANDROID.md) · [Código Android](https://github.com/jabrailkhalil/clickntranslate/tree/android)

## No computador: do texto à tradução

Reconheça uma região, traduza a tela inteira ou o texto selecionado em outro aplicativo. A substituição pode selecionar todo o campo antes de inserir a tradução. O modo dinâmico acompanha várias regiões. Documentos abrem original e tradução lado a lado.

Online: Google, MyMemory, Lingva e LibreTranslate. Offline: Argos Translate e Hy-MT após baixar os modelos. OCR local: Windows OCR, Apple Vision, Tesseract, RapidOCR e EasyOCR, conforme o sistema.

Configure suas chaves OpenAI, Gemini, Claude, DeepL, LibreTranslate ou Custom API em **Settings → Translation and OCR → Language packages → API**. Ao habilitar imagens explicitamente, modelos de visão compatíveis podem reconhecer e traduzir com um único provedor.

O OCR local mantém as imagens no dispositivo. Serviços online recebem o texto; uma API de visão habilitada recebe também a imagem selecionada. Aplicam-se preços e limites do serviço. [Privacidade](../../PRIVACY.md).

Oito idiomas de interface, incluindo português e italiano, com dicas e guia; temas claro e escuro; escala e tamanho do texto do resultado separados; atalhos personalizados; importação/exportação e históricos locais opcionais.

Python está incluído. Windows e Mac usam o certificado autoassinado jabrailkhalil: o SmartScreen pode avisar e o app Mac não é notarizado pela Apple. [Primeiro uso](../guides/setup.en.md). No Mac, conceda gravação de tela e acessibilidade às funções correspondentes. [Linux e atalhos](../LINUX.md).

A versão desktop 1.8.2 baixa atualizações do GitHub Releases dentro do aplicativo. Mac/Linux 1.8.1 e anteriores precisam instalar esta primeira atualização manualmente; locais protegidos podem exigir substituição manual. Versões Store usam a Microsoft Store. Android tem suas próprias [telas e instruções](https://github.com/jabrailkhalil/clickntranslate/tree/android#readme).

[Guia completo em inglês](../../README.md) · [Relatar problema](https://github.com/jabrailkhalil/clickntranslate/issues) · [GPL-3.0](../../LICENSE)

## Mais exemplos

### Copiar texto de uma imagem

![Copiar texto de uma imagem](../images/area-ocr-demo-v2.gif)

### Traduzir o texto selecionado

![Traduzir o texto selecionado](../images/selected-text-demo-v2.gif)

### Traduzir a tela inteira

![Traduzir a tela inteira](../images/fullscreen-translation-demo-v2.gif)

<sub>Gravações da edição desktop; o visual atual das janelas pode ser diferente.</sub>
