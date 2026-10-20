"""Inspect the original and both Orbit sequences at the same frame index."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
if '--export' in sys.argv:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PyQt5 import QtCore, QtGui, QtWidgets
from PIL import Image
from assistant_text import assistant_text

EYES_REVIEW = '--eyes' in sys.argv
CHARACTER = assistant_text('ru', 'orbit')
NAMES = (('Оригинал', 'Прежние глаза', 'Новые глаза') if EYES_REVIEW
         else ('Оригинал', f'{CHARACTER} v16', f'{CHARACTER} v17'))
FRAME_COUNT = 10
COLUMN_WIDTH = 300
SCENE_WIDTH = COLUMN_WIDTH * len(NAMES)
SCENE_HEIGHT = 382


def pixmap_from_pil(image):
    rgba = image.convert('RGBA')
    return QtGui.QPixmap.fromImage(QtGui.QImage(
        rgba.tobytes(), *rgba.size, QtGui.QImage.Format_RGBA8888).copy())


def complete_sequence(folder):
    sequence = [QtGui.QPixmap(str(folder / f'{index:02}.png'))
                for index in range(FRAME_COUNT)]
    return sequence if all(not frame.isNull() for frame in sequence) else []


class Comparison(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'ClicknTranslate — {CHARACTER} · глаза' if EYES_REVIEW
                            else f'ClicknTranslate — {CHARACTER} v17 · кадр в кадр')
        self.resize(960, 530)
        self.frames = [[], [], []]
        source = Image.open(ROOT / 'docs/mascots/reference/original.gif')
        self.durations = []
        for index in range(FRAME_COUNT):
            source.seek(index)
            self.durations.append(source.info.get('duration', 110))
            self.frames[0].append(pixmap_from_pil(
                source.convert('RGBA').crop((27, 37, 99, 109))))
        art = ROOT / 'src/icons/desktop-assistant/orbit'
        previous = (ROOT / 'docs/mascots/orbit-v17-eyes/before' if EYES_REVIEW
                    else art / 'walk-redrawn-frames')
        self.frames[1] = complete_sequence(previous)
        self.frames[2] = complete_sequence(art / 'walk-traced-frames')
        self.index = 0
        self.elapsed = 0.
        self.rate = 1.
        self.light = False
        self.onion = False
        self.overlay = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        heading = QtWidgets.QLabel('Одинаковый кадр и тайминг во всех трёх колонках')
        heading.setStyleSheet('font-size:17px;font-weight:600;')
        layout.addWidget(heading)
        self.scene = QtWidgets.QLabel()
        self.scene.setAlignment(QtCore.Qt.AlignCenter)
        self.scene.setMinimumSize(SCENE_WIDTH, SCENE_HEIGHT)
        layout.addWidget(self.scene, 1)

        controls = QtWidgets.QHBoxLayout()
        self.pause = QtWidgets.QCheckBox('Пауза')
        controls.addWidget(self.pause)
        for label, step in (('← Кадр', -1), ('Кадр →', 1)):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda checked=False, delta=step: self.step(delta))
            controls.addWidget(button)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, FRAME_COUNT - 1)
        self.slider.sliderPressed.connect(lambda: self.pause.setChecked(True))
        self.slider.valueChanged.connect(self.seek)
        controls.addWidget(self.slider, 1)
        speed = QtWidgets.QComboBox()
        for label, value in (('1×', 1.), ('0.5×', .5), ('0.25×', .25)):
            speed.addItem(label, value)
        speed.currentIndexChanged.connect(lambda: setattr(self, 'rate', speed.currentData()))
        controls.addWidget(speed)
        self.caption = QtWidgets.QLabel()
        self.caption.setMinimumWidth(140)
        controls.addWidget(self.caption)
        layout.addLayout(controls)

        options = QtWidgets.QHBoxLayout()
        onion = QtWidgets.QCheckBox('Предыдущий кадр полупрозрачно')
        onion.toggled.connect(lambda value: self.setting('onion', value))
        options.addWidget(onion)
        overlay = QtWidgets.QCheckBox('Оригинал поверх v17')
        overlay.toggled.connect(lambda value: self.setting('overlay', value))
        options.addWidget(overlay)
        light = QtWidgets.QCheckBox('Светлый фон')
        light.toggled.connect(lambda value: self.setting('light', value))
        options.addWidget(light)
        options.addStretch(1)
        layout.addLayout(options)
        for key, delta in ((QtCore.Qt.Key_Left, -1), (QtCore.Qt.Key_Right, 1)):
            shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(key), self)
            shortcut.activated.connect(lambda step=delta: self.step(step))
        self.setStyleSheet(
            'QWidget {background:#22232e;color:#eee8fa;font-family:"Segoe UI";font-size:13px;}'
            'QPushButton,QComboBox {background:#393445;border:1px solid #6e5b83;'
            'border-radius:5px;padding:7px;}')

        self.clock = QtCore.QElapsedTimer()
        self.clock.start()
        self.last_tick_ns = self.clock.nsecsElapsed()
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.draw()

    def setting(self, name, value):
        setattr(self, name, value)
        self.draw()

    def seek(self, index):
        self.index = index
        self.elapsed = 0.
        self.draw()

    def step(self, delta):
        self.pause.setChecked(True)
        self.slider.setValue((self.index + delta) % FRAME_COUNT)

    def tick(self):
        now = self.clock.nsecsElapsed()
        elapsed_ms = (now - self.last_tick_ns) / 1_000_000
        self.last_tick_ns = now
        if self.pause.isChecked() or self.isMinimized():
            return
        self.elapsed += elapsed_ms * self.rate
        while self.elapsed >= self.durations[self.index]:
            self.elapsed -= self.durations[self.index]
            self.index = (self.index + 1) % FRAME_COUNT
        with QtCore.QSignalBlocker(self.slider):
            self.slider.setValue(self.index)
        self.draw()

    def paint_frame(self, painter, column, index, target, onion=False):
        sequence = self.frames[column]
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, column != 0)
        if not sequence:
            painter.drawText(target, QtCore.Qt.AlignCenter | QtCore.Qt.TextWordWrap,
                             'Кадры ещё не готовы\nНужны все 10 PNG')
            return
        if onion:
            previous = sequence[(index - 1) % FRAME_COUNT]
            painter.setOpacity(.22)
            painter.drawPixmap(target, previous, QtCore.QRectF(previous.rect()))
            painter.setOpacity(1)
        frame = sequence[index]
        painter.drawPixmap(target, frame, QtCore.QRectF(frame.rect()))
        if column == 2 and self.overlay:
            reference = self.frames[0][index]
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)
            painter.setOpacity(.22)
            painter.drawPixmap(target, reference, QtCore.QRectF(reference.rect()))
            painter.setOpacity(1)

    def draw(self):
        canvas = QtGui.QPixmap(SCENE_WIDTH, SCENE_HEIGHT)
        canvas.fill(QtGui.QColor('#f4f1f8' if self.light else '#22232e'))
        painter = QtGui.QPainter(canvas)
        painter.setFont(QtGui.QFont('Segoe UI', 11))
        painter.setPen(QtGui.QColor('#362f40' if self.light else '#d6c3f0'))
        for column, name in enumerate(NAMES):
            x = column * COLUMN_WIDTH
            painter.drawText(QtCore.QRectF(x, 3, COLUMN_WIDTH, 26), QtCore.Qt.AlignCenter, name)
            self.paint_frame(painter, column, self.index,
                             QtCore.QRectF(x + 66, 32, 168, 168), self.onion)
            painter.drawText(QtCore.QRectF(x, 204, COLUMN_WIDTH, 24),
                             QtCore.Qt.AlignCenter, '2× · 168 px')
            self.paint_frame(painter, column, self.index,
                             QtCore.QRectF(x + 108, 244, 84, 84), self.onion)
            painter.drawText(QtCore.QRectF(x, 336, COLUMN_WIDTH, 24),
                             QtCore.Qt.AlignCenter, '1× · 84 px')
        painter.end()
        self.scene.setPixmap(canvas)
        self.caption.setText(f'{self.index:02}/09 · {self.durations[self.index]} мс')


def pil_from_pixmap(pixmap):
    image = pixmap.toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
    pointer = image.bits()
    pointer.setsize(image.byteCount())
    return Image.frombytes('RGBA', (image.width(), image.height()), bytes(pointer))


def export(window):
    output = ROOT / ('docs/mascots/orbit-v17-eyes' if EYES_REVIEW
                     else 'docs/mascots/orbit-v17')
    output.mkdir(parents=True, exist_ok=True)
    window.timer.stop()
    window.pause.setChecked(True)
    images = []
    for index in range(FRAME_COUNT):
        window.slider.setValue(index)
        window.draw()
        QtWidgets.QApplication.processEvents()
        images.append(pil_from_pixmap(window.grab()).convert('RGB'))
    palette_source = Image.new('RGB', (images[0].width * FRAME_COUNT, images[0].height))
    for index, frame in enumerate(images):
        palette_source.paste(frame, (index * frame.width, 0))
    palette = palette_source.quantize(colors=256)
    frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in images]
    frames[0].save(output / 'comparison.gif', save_all=True, append_images=frames[1:],
                   duration=window.durations, loop=0)

    sheet = QtGui.QPixmap(1380, 3 * 160 + 36)
    sheet.fill(QtGui.QColor('#22232e'))
    painter = QtGui.QPainter(sheet)
    painter.setPen(QtGui.QColor('#d6c3f0'))
    painter.setFont(QtGui.QFont('Segoe UI', 10))
    for index in range(FRAME_COUNT):
        painter.drawText(QtCore.QRectF(100 + index * 128, 2, 128, 26),
                         QtCore.Qt.AlignCenter, f'{index:02} · {window.durations[index]} ms')
    for column, name in enumerate(NAMES):
        y = 36 + column * 160
        painter.drawText(QtCore.QRectF(2, y, 94, 128),
                         QtCore.Qt.AlignCenter | QtCore.Qt.TextWordWrap, name)
        for index in range(FRAME_COUNT):
            window.paint_frame(painter, column, index,
                               QtCore.QRectF(100 + index * 128, y, 128, 128))
    painter.end()
    sheet.save(str(output / 'poses.png'))
    print(output / 'comparison.gif', flush=True)
    print(output / 'poses.png', flush=True)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    if '--export' in sys.argv:
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/segoeui.ttf'
        if font.is_file():
            QtGui.QFontDatabase.addApplicationFont(str(font))
    window = Comparison()
    window.show()
    if '--export' in sys.argv:
        export(window)
    else:
        def ready():
            target = ROOT / ('.tmp/orbit-eyes-window.png' if EYES_REVIEW
                             else '.tmp/orbit-v17-window.png')
            target.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(target))
            missing = ', '.join(NAMES[index] for index, frames in enumerate(window.frames) if not frames)
            print('Opened Orbit v17 frame comparison' + (f'; missing: {missing}' if missing else ''), flush=True)
        QtCore.QTimer.singleShot(700, ready)
        sys.exit(app.exec_())
