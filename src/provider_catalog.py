"""Provider IDs and labels shared by settings, results, documents and recovery."""
TRANSLATION_PROVIDERS = (
    ('google', 'Google', 'online'),
    ('argos', 'Argos', 'offline'),
    ('hymt', 'Hy-MT', 'offline'),
    ('mymemory', 'MyMemory', 'online'),
    ('lingva', 'Lingva', 'online'),
    ('libretranslate', 'LibreTranslate', 'online'),
    ('openai', 'OpenAI', 'api'),
    ('openai-compatible', 'Custom API', 'api'),
    ('gemini', 'Gemini', 'api'),
    ('anthropic', 'Claude', 'api'),
    ('deepl', 'DeepL API', 'api'),
)


def provider_id(value):
    normalized = str(value or '').strip().lower()
    return next((key for key, name, _kind in TRANSLATION_PROVIDERS
                 if normalized in (key, name.lower())), normalized)
