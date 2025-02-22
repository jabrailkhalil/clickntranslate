import asyncio
import os
import winrt

from PIL import Image
from winrt.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage import StorageFile, FileAccessMode
import winrt.windows.storage.streams as streams

async def load_image_file_native(file_path):
    file = await StorageFile.get_file_from_path_async(os.fspath(file_path))
    stream = await file.open_async(FileAccessMode.READ)
    decoder = await BitmapDecoder.create_async(stream)
    return await decoder.get_software_bitmap_async()

def load_image_file_pillow(file_path):
    image = Image.open(file_path).convert("RGBA")
    data_writer = streams.DataWriter()
    bytes = image.tobytes()
    data_writer.write_bytes(list(bytes))
    bitmap = SoftwareBitmap(BitmapPixelFormat.RGBA8, image.width, image.height)
    bitmap.copy_from_buffer(data_writer.detach_buffer())
    return bitmap

async def run_ocr(bitmap):
    engine = OcrEngine.try_create_from_user_profile_languages()
    return await engine.recognize_async(bitmap)

async def async_main():
    screenshot_path = r"img.png"
    # bitmap = await load_image_file_native(screenshot_path)
    bitmap = load_image_file_pillow(screenshot_path)
    result = await run_ocr(bitmap)
    print(result.text)

asyncio.run(async_main())