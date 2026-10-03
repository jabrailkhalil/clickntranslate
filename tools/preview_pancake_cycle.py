"""Python-only comparison of the reference, drawn v8 and the v9-v15 rig.

No app settings or production artwork are changed. --export saves review media.
"""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
if '--export' in sys.argv:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt5 import QtCore, QtGui, QtWidgets
from assistant_reference_motion import paint_pancake, CYCLE_SECONDS


class Scene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        from PIL import Image
        self.setMinimumSize(870, 300)
        self.phase = 0.
        self.quantized = False
        self.landmarks = False
        self.facing = 1
        self.extent = 192
        self.version = 'v15'
        self.background = '#22232e'
        self.original = []
        self.previous = []
        original = Image.open(ROOT/'docs/mascots/reference/original.gif')
        for index in range(original.n_frames):
            original.seek(index)
            frame = original.convert('RGBA').crop((30, 43, 96, 109))
            image = QtGui.QImage(frame.tobytes(), *frame.size, QtGui.QImage.Format_RGBA8888).copy()
            self.original.append(QtGui.QPixmap.fromImage(image))
            self.previous.append(QtGui.QPixmap(str(ROOT/'src/icons/desktop-assistant'
                /'pancake/walk-reference-frames'/f'{index:02}.png')))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        background = QtGui.QColor(self.background)
        painter.fillRect(self.rect(), background)
        dark = background.lightnessF() < .5
        painter.setFont(QtGui.QFont('Segoe UI', 12))
        width = self.width()/3
        size = min(float(self.extent), width-48.)
        top = 60.+(230.-size)*120/128
        index = int((self.phase % 1.)*10) % 10
        names = {'v15': 'Перекрытие на шаге назад', 'v14': 'Объём и перекрытие ног', 'v13': 'С мягкой тенью',
                 'v12': 'Рука и пропорции', 'v11': 'Мягче переходы',
                 'v10': 'Живее шаг', 'v9': 'Первая плавная проба'}
        titles = ('Оригинал', 'Рисованные позы', names[self.version])
        for column, title in enumerate(titles):
            x = column*width+(width-size)/2
            painter.setPen(QtGui.QColor('#eee8fa' if dark else '#362f40'))
            painter.drawText(QtCore.QRectF(column*width, 12, width, 28), QtCore.Qt.AlignCenter, title)
            rect = QtCore.QRectF(x, top, size, size)
            painter.setPen(QtGui.QColor('#505264' if dark else '#94919c'))
            painter.drawLine(QtCore.QPointF(x-8, top+size*120/128),
                             QtCore.QPointF(x+size+8, top+size*120/128))
            if column == 2:
                phase = index/10 if self.quantized else self.phase
                paint_pancake(painter, rect, phase, self.facing, self.landmarks, self.version)
            else:
                frame = self.original[index] if column == 0 else self.previous[index]
                painter.save()
                painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, column != 0)
                if self.facing < 0:
                    painter.translate(rect.center().x()*2., 0.)
                    painter.scale(-1., 1.)
                painter.drawPixmap(rect, frame, QtCore.QRectF(frame.rect()))
                painter.restore()
        painter.end()


class Preview(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ClicknTranslate — Блинчик · доработка ноги · Python')
        self.resize(1000, 460)
        self.rate = 1.
        self.elapsed = 0.
        layout = QtWidgets.QVBoxLayout(self)
        heading = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('Блинчик: доработка ноги')
        title.setStyleSheet('font-size:18px;font-weight:600;padding:8px;')
        heading.addWidget(title, 1)
        version = QtWidgets.QComboBox()
        version.addItem('Справа: доработка ноги v15', 'v15')
        version.addItem('Справа: объём и тень v14', 'v14')
        version.addItem('Справа: с тенью v13', 'v13')
        version.addItem('Справа: рука и пропорции v12', 'v12')
        version.addItem('Справа: мягче переходы v11', 'v11')
        version.addItem('Справа: доработка v10', 'v10')
        version.addItem('Справа: первая проба v9', 'v9')
        version.currentIndexChanged.connect(lambda: self.setting('version', version.currentData()))
        heading.addWidget(version)
        layout.addLayout(heading)
        self.scene = Scene()
        layout.addWidget(self.scene, 1)
        row = QtWidgets.QHBoxLayout()
        self.pause = QtWidgets.QCheckBox('Пауза')
        row.addWidget(self.pause)
        for label, delta in (('← Поза', -1), ('Поза →', 1)):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _, d=delta: self.step(d))
            row.addWidget(button)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 1099)
        self.slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.slider.setTickInterval(110)
        self.slider.sliderPressed.connect(lambda: self.pause.setChecked(True))
        self.slider.valueChanged.connect(self.seek)
        row.addWidget(self.slider, 1)
        rate = QtWidgets.QComboBox()
        for text, value in (('1×', 1.), ('0.5×', .5), ('0.25×', .25)):
            rate.addItem(text, value)
        rate.currentIndexChanged.connect(lambda: setattr(self, 'rate', rate.currentData()))
        row.addWidget(rate)
        layout.addLayout(row)
        row = QtWidgets.QHBoxLayout()
        poses = QtWidgets.QCheckBox('Новый: только 10 опорных поз')
        poses.toggled.connect(lambda v: self.setting('quantized', v))
        row.addWidget(poses)
        points = QtWidgets.QCheckBox('Показать опоры')
        points.toggled.connect(lambda v: self.setting('landmarks', v))
        row.addWidget(points)
        left = QtWidgets.QCheckBox('Влево')
        left.toggled.connect(lambda v: self.setting('facing', -1 if v else 1))
        row.addWidget(left)
        sizes = QtWidgets.QComboBox()
        for value in (100, 128, 192, 230):
            sizes.addItem(f'{value} px', value)
        sizes.setCurrentIndex(2)
        sizes.currentIndexChanged.connect(lambda: self.setting('extent', sizes.currentData()))
        row.addWidget(sizes)
        backgrounds = QtWidgets.QComboBox()
        for text, color in (('Тёмный фон', '#22232e'), ('Серый фон', '#a5a7b1'),
                            ('Светлый фон', '#f4f1f8')):
            backgrounds.addItem(text, color)
        backgrounds.currentIndexChanged.connect(
            lambda: self.setting('background', backgrounds.currentData()))
        row.addWidget(backgrounds)
        row.addStretch(1)
        self.caption = QtWidgets.QLabel()
        row.addWidget(self.caption)
        layout.addLayout(row)
        self.setStyleSheet('QWidget {background:#22232e;color:#eee8fa;font-family:"Segoe UI";font-size:13px;}'
            'QPushButton,QComboBox {background:#393445;border:1px solid #6e5b83;border-radius:5px;padding:7px;}')
        self.clock = QtCore.QElapsedTimer()
        self.clock.start()
        self.last_tick_ns = self.clock.nsecsElapsed()
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        refresh = self.screen().refreshRate() if self.screen() is not None else 60.
        # Offer a fresh pose at least twice per display refresh. A fixed 16 ms
        # timer drifts against 60 Hz and can leave a repeated display frame.
        self.timer.setInterval(max(4, round(500./max(30., refresh))))
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.seek(0)

    def setting(self, name, value):
        setattr(self.scene, name, value)
        self.scene.update()

    def seek(self, milliseconds):
        self.elapsed = milliseconds/1000.
        self.scene.phase = self.elapsed/CYCLE_SECONDS
        self.caption.setText(f'{milliseconds:04} / 1100 мс')
        self.scene.update()

    def step(self, delta):
        self.pause.setChecked(True)
        index = (int(self.scene.phase*10+1e-7)+delta) % 10
        self.slider.setValue(index*110)

    def tick(self):
        now_ns = self.clock.nsecsElapsed()
        dt = (now_ns-self.last_tick_ns)/1_000_000_000.
        self.last_tick_ns = now_ns
        if self.pause.isChecked() or self.isMinimized():
            return
        elapsed = (self.elapsed+dt*self.rate) % CYCLE_SECONDS
        # Keep the fractional clock; integer slider positions are display only.
        with QtCore.QSignalBlocker(self.slider):
            self.slider.setValue(int(elapsed*1000))
        self.elapsed = elapsed
        self.scene.phase = elapsed/CYCLE_SECONDS
        self.caption.setText(f'{int(elapsed*1000):04} / 1100 мс')
        self.scene.update()


def export(window):
    from PIL import Image
    output = ROOT/'docs/mascots/pancake-cycle-v15'
    output.mkdir(parents=True, exist_ok=True)
    window.timer.stop()
    window.resize(1000, 460)
    window.show()
    QtWidgets.QApplication.processEvents()
    frames = []
    # GIF delays are multiples of 10 ms. These five samples preserve the
    # reference's exact 110 ms holds without using a browser-clamped 10 ms frame.
    sample_times = [key*110+offset for key in range(10) for offset in (0, 20, 40, 60, 80)]
    durations = [20, 20, 20, 20, 30]*10
    for milliseconds in sample_times:
        window.slider.setValue(milliseconds)
        QtWidgets.QApplication.processEvents()
        image = window.scene.grab().toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
        pointer = image.bits()
        pointer.setsize(image.byteCount())
        frames.append(Image.frombytes('RGBA', (image.width(), image.height()), bytes(pointer)).convert('RGB'))
    palette_source = Image.new('RGB', (frames[0].width*5, frames[0].height))
    for column, index in enumerate((0, 10, 20, 30, 40)):
        palette_source.paste(frames[index], (column*frames[0].width, 0))
    palette = palette_source.quantize(colors=256)
    encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    encoded[0].save(output/'comparison.gif', save_all=True, append_images=encoded[1:], duration=durations, loop=0)
    sheet = QtGui.QImage(1920, 610, QtGui.QImage.Format_RGBA8888)
    sheet.fill(QtGui.QColor('#22232e'))
    painter = QtGui.QPainter(sheet)
    painter.setFont(QtGui.QFont('Segoe UI', 11))
    for index in range(10):
        painter.drawPixmap(QtCore.QRectF(index*192, 0, 192, 192), window.scene.previous[index],
                           QtCore.QRectF(window.scene.previous[index].rect()))
        paint_pancake(painter, QtCore.QRectF(index*192, 202, 192, 192), index/10, version='v13')
        paint_pancake(painter, QtCore.QRectF(index*192, 402, 192, 192), index/10)
        painter.setPen(QtGui.QColor('#eee8fa'))
        painter.drawText(index*192+82, 605, str(index))
    painter.end()
    sheet.save(str(output/'poses.png'))
    seam = QtGui.QImage(1536, 220, QtGui.QImage.Format_RGBA8888)
    seam.fill(QtGui.QColor('#22232e'))
    painter = QtGui.QPainter(seam)
    painter.setFont(QtGui.QFont('Segoe UI', 11))
    for column, phase in enumerate((.8, .85, .9, .95, 1., 1.05, 1.1, 1.15)):
        paint_pancake(painter, QtCore.QRectF(column*192, 0, 192, 192), phase)
        painter.setPen(QtGui.QColor('#eee8fa'))
        painter.drawText(column*192+60, 212, f'{round(phase*1100)} ms')
    painter.end()
    seam.save(str(output/'loop-seam.png'))
    overlap = QtGui.QImage(1536, 420, QtGui.QImage.Format_RGBA8888)
    overlap.fill(QtGui.QColor('#22232e'))
    painter = QtGui.QPainter(overlap)
    painter.setFont(QtGui.QFont('Segoe UI', 10))
    for row, start in enumerate((.18, .40)):
        for column in range(8):
            phase = start+column*.02
            paint_pancake(painter, QtCore.QRectF(column*192, row*210, 192, 192), phase)
            painter.setPen(QtGui.QColor('#eee8fa'))
            painter.drawText(column*192+60, row*210+206, f'{round(phase*1100)} ms')
    painter.end()
    overlap.save(str(output/'leg-overlap.png'))
    backgrounds = QtGui.QImage(768, 240, QtGui.QImage.Format_RGBA8888)
    painter = QtGui.QPainter(backgrounds)
    painter.setFont(QtGui.QFont('Segoe UI', 10))
    for column, (color, phase) in enumerate((('#22232e', 0.), ('#22232e', .8),
                                            ('#f4f1f8', 0.), ('#f4f1f8', .8))):
        painter.fillRect(column*192, 0, 192, 240, QtGui.QColor(color))
        paint_pancake(painter, QtCore.QRectF(column*192, 8, 192, 192), phase)
        painter.setPen(QtGui.QColor('#eee8fa' if column < 2 else '#362f40'))
        painter.drawText(QtCore.QRectF(column*192, 207, 192, 24), QtCore.Qt.AlignCenter,
                         'Опора' if phase == 0. else 'Перенос ноги')
    painter.end()
    backgrounds.save(str(output/'shadow-backgrounds.png'))
    window.grab().save(str(output/'window.png'))
    print(output/'comparison.gif')


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    # The Windows offscreen backend does not populate the system font database.
    if '--export' in sys.argv:
        fonts = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts'
        for filename in ('segoeui.ttf', 'segoeuib.ttf'):
            path = fonts/filename
            if path.exists():
                QtGui.QFontDatabase.addApplicationFont(str(path))
        app.setFont(QtGui.QFont('Segoe UI', 10))
    window = Preview()
    window.show()
    if '--export' in sys.argv:
        export(window)
    else:
        def ready():
            target = ROOT/'.tmp/pancake-cycle-window.png'
            target.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(target))
            print('Opened pancake comparison', flush=True)
        QtCore.QTimer.singleShot(700, ready)
        sys.exit(app.exec_())
