"""Offline Apple Vision OCR with the same geometry contract as other engines."""

from functools import lru_cache
import io

from ocr_text_layout import order_ocr_items


@lru_cache(maxsize=1)
def supported_languages():
    import objc
    import Vision
    with objc.autorelease_pool():
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        languages, error = request.supportedRecognitionLanguagesAndReturnError_(None)
        if error:
            raise RuntimeError(str(error))
        return tuple(str(language) for language in languages or ())


def language_codes():
    # Language availability depends on macOS, not on an invented fixed list.
    from languages import LANGUAGES as APP_LANGUAGES
    supported = {tag.split("-")[0].lower() for tag in supported_languages()}
    return [language.code for language in APP_LANGUAGES if language.code.split("-")[0] in supported]


def recognition_languages(code, supported):
    code = str(code or "auto").lower()
    if code in {"auto", "universal"}:
        return []
    matches = [tag for tag in supported if tag.lower() == code or tag.split("-")[0].lower() == code]
    if not matches:
        raise ValueError(f"Apple Vision on this macOS version does not support OCR language {code!r}.")
    english = next((tag for tag in supported if tag.startswith("en-")), None)
    return matches[:1] + ([english] if english and english not in matches[:1] else [])


def pixel_box(rect, width, height):
    """Vision uses a lower-left origin; OCR layout uses top-left pixel corners."""
    x, y = rect.origin.x, rect.origin.y
    w, h = rect.size.width, rect.size.height
    left, top = max(0.0, x * width), max(0.0, (1.0 - y - h) * height)
    right, bottom = min(float(width), (x + w) * width), min(float(height), (1.0 - y) * height)
    return [[left, top], [right, top], [right, bottom], [left, bottom]]


def recognize_image(image, language="auto"):
    import objc
    import Foundation
    import Vision
    stream = io.BytesIO()
    image.convert("RGB").save(stream, format="PNG")
    payload = stream.getvalue()
    with objc.autorelease_pool():
        data = Foundation.NSData.dataWithBytes_length_(payload, len(payload))
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setUsesLanguageCorrection_(True)
        languages = recognition_languages(language, supported_languages())
        if languages:
            request.setRecognitionLanguages_(languages)
        else:
            request.setAutomaticallyDetectsLanguage_(True)
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, {})
        succeeded, error = handler.performRequests_error_([request], None)
        if not succeeded or error:
            raise RuntimeError(str(error or "Apple Vision recognition failed."))
        items = []
        for observation in request.results() or ():
            candidates = observation.topCandidates_(1)
            if not candidates:
                continue
            candidate = candidates[0]
            text = str(candidate.string()).strip()
            if text:
                items.append((pixel_box(observation.boundingBox(), *image.size), text, float(candidate.confidence())))
        return order_ocr_items(items)
