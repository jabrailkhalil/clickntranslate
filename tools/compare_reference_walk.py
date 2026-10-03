"""Visual, synchronized comparison against the original local GIF."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if '--export' in sys.argv:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt5 import QtCore, QtGui, QtWidgets

NAMES = ('Оригинал', 'Блинчик', 'Моти', 'Момо', 'Орбит')
IDS = ('pancake', 'mochi', 'momo', 'orbit')


class Comparison(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        from PIL import Image
        self.setWindowTitle('ClicknTranslate — исходный GIF и наши герои · кадр в кадр')
        self.resize(1060, 380)
        self.frames = [[] for _ in NAMES]
        original = Image.open(ROOT / 'docs/mascots/reference/original.gif')
        self.durations = []
        for index in range(original.n_frames):
            original.seek(index)
            self.durations.append(original.info['duration'])
            frame = original.convert('RGBA').crop((30, 43, 96, 109))
            data = frame.tobytes()
            qimage = QtGui.QImage(data, *frame.size, QtGui.QImage.Format_RGBA8888).copy()
            self.frames[0].append(QtGui.QPixmap.fromImage(qimage))
            for column, name in enumerate(IDS, 1):
                self.frames[column].append(QtGui.QPixmap(str(ROOT / 'src/icons/desktop-assistant'
                    / name / 'walk-reference-frames' / f'{index:02}.png')))
        self.index = 0
        self.elapsed = 0.
        self.rate = 1.
        self.paused = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        title = QtWidgets.QLabel('Один номер кадра у оригинала и всех четырёх героев')
        title.setStyleSheet('font-size:18px;font-weight:600;')
        layout.addWidget(title)
        self.scene = QtWidgets.QLabel()
        self.scene.setMinimumHeight(240)
        layout.addWidget(self.scene, 1)
        controls = QtWidgets.QHBoxLayout()
        pause = QtWidgets.QCheckBox('Пауза')
        pause.toggled.connect(lambda value: setattr(self, 'paused', value))
        controls.addWidget(pause)
        for label, step in (('← Кадр', -1), ('Кадр →', 1)):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _, delta=step: self.step(delta, pause))
            controls.addWidget(button)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, len(self.durations)-1)
        self.slider.sliderPressed.connect(lambda: pause.setChecked(True))
        self.slider.valueChanged.connect(self.seek)
        controls.addWidget(self.slider, 1)
        rate = QtWidgets.QComboBox()
        for label, value in (('1×', 1.), ('0.5×', .5), ('0.25×', .25)):
            rate.addItem(label, value)
        rate.currentIndexChanged.connect(lambda: setattr(self, 'rate', rate.currentData()))
        controls.addWidget(rate)
        self.caption = QtWidgets.QLabel()
        controls.addWidget(self.caption)
        layout.addLayout(controls)
        self.setStyleSheet('QWidget {background:#22232e;color:#eee8fa;font-family:"Segoe UI";font-size:13px;}'
            'QPushButton,QComboBox {background:#393445;border:1px solid #6e5b83;border-radius:5px;padding:7px;}')
        self.clock = QtCore.QElapsedTimer()
        self.clock.start()
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.draw()

    def seek(self, value):
        self.index = value
        self.elapsed = 0.
        self.draw()

    def step(self, delta, pause):
        pause.setChecked(True)
        self.slider.setValue((self.index+delta) % len(self.durations))

    def tick(self):
        dt = self.clock.restart()
        if self.paused or self.isMinimized():
            return
        self.elapsed += dt*self.rate
        while self.elapsed >= self.durations[self.index]:
            self.elapsed -= self.durations[self.index]
            self.index = (self.index+1) % len(self.durations)
        with QtCore.QSignalBlocker(self.slider):
            self.slider.setValue(self.index)
        self.draw()

    def draw(self):
        canvas = QtGui.QPixmap(1010, 240)
        canvas.fill(QtGui.QColor('#22232e'))
        painter = QtGui.QPainter(canvas)
        painter.setFont(QtGui.QFont('Segoe UI', 11))
        for column, frames in enumerate(self.frames):
            x = column*202
            painter.setPen(QtGui.QColor('#d6c3f0'))
            painter.drawText(QtCore.QRectF(x, 4, 202, 24), QtCore.Qt.AlignCenter, NAMES[column])
            frame = frames[self.index]
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, column != 0)
            painter.drawPixmap(QtCore.QRectF(x+5, 32, 192, 192), frame, QtCore.QRectF(frame.rect()))
        painter.end()
        self.scene.setPixmap(canvas)
        self.caption.setText(f'{self.index+1}/10 · {self.durations[self.index]} мс')


def export(window):
    from PIL import Image
    output = ROOT / 'docs/mascots'
    sys.path.insert(0, str(ROOT / 'tests'))
    from qt_layout_test_support import ensure_layout_fonts
    ensure_layout_fonts(QtWidgets.QApplication.instance())
    window.timer.stop()
    images = []
    for index in range(len(window.durations)):
        window.slider.setValue(index)
        window.draw()
        QtWidgets.QApplication.processEvents()
        canvas = window.grab().toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
        pointer = canvas.bits()
        pointer.setsize(canvas.byteCount())
        images.append(Image.frombytes('RGBA', (canvas.width(), canvas.height()), bytes(pointer)).convert('RGB'))
    palette = images[0].quantize(colors=256)
    frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    frames[0].save(output / 'reference-comparison-v8.gif', save_all=True, append_images=frames[1:],
                   duration=window.durations, loop=0)
    sheet = QtGui.QPixmap(2040, 1020)
    sheet.fill(QtGui.QColor('#22232e'))
    painter = QtGui.QPainter(sheet)
    painter.setFont(QtGui.QFont('Segoe UI', 10))
    for row, sequence in enumerate(window.frames):
        painter.setPen(QtGui.QColor('#d6c3f0'))
        painter.drawText(8, row*200+98, NAMES[row])
        for index, frame in enumerate(sequence):
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, row != 0)
            painter.drawPixmap(QtCore.QRectF(110+index*192, row*200, 192, 192),
                               frame, QtCore.QRectF(frame.rect()))
            if row == 4:
                painter.drawText(180+index*192, 1010, f'{index:02} · 110 ms')
    painter.end()
    sheet.save(str(output / 'reference-poses-v8.png'))
    print(output / 'reference-comparison-v8.gif')


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Comparison()
    window.show()
    if '--export' in sys.argv:
        export(window)
    else:
        sys.exit(app.exec_())
