"""EasyOCR 1.7.2 model families, usable without importing its native SDK.

Mapping follows JaidedAI/EasyOCR at c4f3cd7225efd4f85451bd8b4a7646ae9a092420.
English fallback is inside the chosen recognition network, not a second model.
"""
from pathlib import Path

SDK_ALIASES = {'nb': 'no', 'sr': 'rs_cyrillic', 'zh': 'ch_sim', 'zh-hant': 'ch_tra', 'zh-tw': 'ch_tra'}

LANGUAGE_GROUPS = {'abq': 'cyrillic_g2',
 'ady': 'cyrillic_g2',
 'af': 'latin_g2',
 'ang': 'devanagari',
 'ar': 'arabic',
 'as': 'bengali',
 'ava': 'cyrillic_g2',
 'az': 'latin_g2',
 'be': 'cyrillic_g2',
 'bg': 'cyrillic_g2',
 'bgc': 'devanagari',
 'bh': 'devanagari',
 'bho': 'devanagari',
 'bn': 'bengali',
 'bs': 'latin_g2',
 'ch_sim': 'zh_sim_g2',
 'ch_tra': 'zh_tra',
 'che': 'cyrillic_g2',
 'cs': 'latin_g2',
 'cy': 'latin_g2',
 'da': 'latin_g2',
 'dar': 'cyrillic_g2',
 'de': 'latin_g2',
 'en': 'english_g2',
 'es': 'latin_g2',
 'et': 'latin_g2',
 'fa': 'arabic',
 'fr': 'latin_g2',
 'ga': 'latin_g2',
 'gom': 'devanagari',
 'hi': 'devanagari',
 'hr': 'latin_g2',
 'hu': 'latin_g2',
 'id': 'latin_g2',
 'inh': 'cyrillic_g2',
 'is': 'latin_g2',
 'it': 'latin_g2',
 'ja': 'japanese_g2',
 'kbd': 'cyrillic_g2',
 'kn': 'kannada_g2',
 'ko': 'korean_g2',
 'ku': 'latin_g2',
 'la': 'latin_g2',
 'lbe': 'cyrillic_g2',
 'lez': 'cyrillic_g2',
 'lt': 'latin_g2',
 'lv': 'latin_g2',
 'mah': 'devanagari',
 'mai': 'devanagari',
 'mi': 'latin_g2',
 'mn': 'cyrillic_g2',
 'mni': 'bengali',
 'mr': 'devanagari',
 'ms': 'latin_g2',
 'mt': 'latin_g2',
 'nb': 'latin_g2',
 'ne': 'devanagari',
 'new': 'devanagari',
 'nl': 'latin_g2',
 'no': 'latin_g2',
 'oc': 'latin_g2',
 'pi': 'latin_g2',
 'pl': 'latin_g2',
 'pt': 'latin_g2',
 'ro': 'latin_g2',
 'rs_cyrillic': 'cyrillic_g2',
 'rs_latin': 'latin_g2',
 'ru': 'cyrillic_g2',
 'sa': 'devanagari',
 'sck': 'devanagari',
 'sk': 'latin_g2',
 'sl': 'latin_g2',
 'sq': 'latin_g2',
 'sr': 'cyrillic_g2',
 'sv': 'latin_g2',
 'sw': 'latin_g2',
 'ta': 'tamil',
 'tab': 'cyrillic_g2',
 'te': 'telugu_g2',
 'th': 'thai',
 'tjk': 'cyrillic_g2',
 'tl': 'latin_g2',
 'tr': 'latin_g2',
 'ug': 'arabic',
 'uk': 'cyrillic_g2',
 'ur': 'arabic',
 'uz': 'latin_g2',
 'vi': 'latin_g2',
 'zh': 'zh_sim_g2',
 'zh-hant': 'zh_tra',
 'zh-tw': 'zh_tra'}

MODEL_FILES = {'arabic': 'arabic.pth',
 'bengali': 'bengali.pth',
 'cyrillic_g2': 'cyrillic_g2.pth',
 'devanagari': 'devanagari.pth',
 'english_g2': 'english_g2.pth',
 'japanese_g2': 'japanese_g2.pth',
 'kannada_g2': 'kannada.pth',
 'korean_g2': 'korean_g2.pth',
 'latin_g2': 'latin_g2.pth',
 'tamil': 'tamil.pth',
 'telugu_g2': 'telugu.pth',
 'thai': 'thai.pth',
 'zh_sim_g2': 'zh_sim_g2.pth',
 'zh_tra': 'chinese.pth'}

MODEL_FILE_VARIANTS = {'arabic': ('arabic.pth',),
 'bengali': ('bengali.pth',),
 'cyrillic_g2': ('cyrillic_g2.pth', 'cyrillic.pth'),
 'devanagari': ('devanagari.pth',),
 'english_g2': ('english_g2.pth',),
 'japanese_g2': ('japanese_g2.pth', 'japanese.pth'),
 'kannada_g2': ('kannada.pth',),
 'korean_g2': ('korean_g2.pth', 'korean.pth'),
 'latin_g2': ('latin_g2.pth', 'latin.pth'),
 'tamil': ('tamil.pth',),
 'telugu_g2': ('telugu.pth',),
 'thai': ('thai.pth',),
 'zh_sim_g2': ('zh_sim_g2.pth', 'chinese_sim.pth'),
 'zh_tra': ('chinese.pth',)}

PROBE_CODES = {'arabic': 'ar',
 'bengali': 'bn',
 'cyrillic_g2': 'ru',
 'devanagari': 'hi',
 'english_g2': 'en',
 'japanese_g2': 'ja',
 'kannada_g2': 'kn',
 'korean_g2': 'ko',
 'latin_g2': 'de',
 'tamil': 'ta',
 'telugu_g2': 'te',
 'thai': 'th',
 'zh_sim_g2': 'ch_sim',
 'zh_tra': 'ch_tra'}


def group_for_language(code):
    return LANGUAGE_GROUPS.get(str(code).lower())


def installed_groups(root, legacy=False, model_files=None):
    model_dir = Path(root) / 'models'
    return {group for group, filename in (MODEL_FILES if model_files is None else model_files).items()
            if isinstance(filename,str) and Path(filename).name == filename
            if any((model_dir / name).is_file() for name in
                   (MODEL_FILE_VARIANTS[group] if legacy else (filename,)))}


def installed_languages(root, codes, *, model_files=None, language_groups=None):
    if not (Path(root) / 'models/craft_mlt_25k.pth').is_file():
        return []
    groups = installed_groups(root,model_files=model_files)
    mapping = LANGUAGE_GROUPS if language_groups is None else language_groups
    return [code for code in codes if mapping.get(code) in groups]


# Released upstream alphabet for the original v1.1.7 Tamil weights.
# EasyOCR 1.7.2 accidentally removed 16 symbols while keeping those weights.
TAMIL_ALPHABET_FIX = {
  "filename": "tamil.pth",
  "url": "https://github.com/JaidedAI/EasyOCR/releases/download/v1.1.7/tamil.zip",
  "characters": "0123456789!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ\u0b83\u0b85\u0b86\u0b87\u0b88\u0b89\u0b8a\u0b8e\u0b8f\u0b90\u0b92\u0b93\u0b94\u0b95\u0b99\u0b9a\u0b9c\u0b9e\u0b9f\u0ba3\u0ba4\u0ba8\u0ba9\u0baa\u0bae\u0baf\u0bb0\u0bb1\u0bb2\u0bb3\u0bb4\u0bb5\u0bb7\u0bb8\u0bb9\u0bbe\u0bbf\u0bc0\u0bc1\u0bc2\u0bc6\u0bc7\u0bc8\u0bca\u0bcb\u0bcc\u0bcd",
  "source_commit": "11fa4b123786fbec78ce6fb70abd1d27705223af",
  "source_sha256": "660713fac3c98a84949bc21d4baf8aa27aaac9225f42684e2f40b3e0dea701c0",
  "source_url": "https://raw.githubusercontent.com/JaidedAI/EasyOCR/11fa4b123786fbec78ce6fb70abd1d27705223af/easyocr/config.py",
  "model_md5": "4b93972fdacdcdabe6d57097025d4dc2"
}
