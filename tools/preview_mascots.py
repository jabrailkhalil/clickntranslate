"""Interactive Python-only visual workshop for the production mascot renderer.

No application settings, hotkeys, translation workers, packaging or tests.
Run: .venv/Scripts/python.exe tools/preview_mascots.py
"""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
if '--export' in sys.argv:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt5 import QtCore, QtGui, QtWidgets
from assistant_art import MASCOTS
from assistant_motion import PetMotion, paint_pet, WALK_FRAME_NAMES, WALK_FRAME_DURATIONS

NAMES = ('Блинчик', 'Моти', 'Бубу', 'Момо', 'Орбит')
REVISION = 'v8'
STATES = (
    ('Прогулка / ползание', 'walk', 'neutral'),
    ('Спокойный', 'idle', 'neutral'), ('Радостный', 'idle', 'happy'),
    ('Любопытный', 'idle', 'curious'), ('Думает', 'idle', 'thinking'),
    ('Удивлён', 'idle', 'surprised'), ('Грустный', 'idle', 'sad'),
    ('Сонный', 'idle', 'sleepy'), ('Спит', 'sleep', 'neutral'),
    ('Гордится', 'proud', 'neutral'), ('Машет', 'wave', 'neutral'),
    ('Во время перевода', 'work', 'neutral'), ('Перевод готов', 'success', 'neutral'),
    ('Ошибка перевода', 'error', 'neutral'),
)


class Scene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(690, 605)
        self.pets = [PetMotion(m) for m in MASCOTS]
        self.positions = [150.] * 5
        self.directions = [1] * 5
        self.state = 0
        self.speed = 40
        self.extent = 128
        self.rate = 1.
        self.paused = False
        self.dark = True
        self.clock = QtCore.QElapsedTimer()
        self.clock.start()
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def reset(self):
        self.pets = [PetMotion(m) for m in MASCOTS]
        self.positions = [150.] * 5
        self.directions = [1] * 5
        self.update()

    def tick(self):
        dt = min(.08, self.clock.restart()/1000) * self.rate
        if self.paused or not self.isVisible() or self.window().isMinimized():
            return
        self.advance(dt)

    def advance(self, dt):
        action = STATES[self.state][1]
        for index, pet in enumerate(self.pets):
            if action == 'walk':
                pet.reactions = False
                delta = pet.advance(dt, self.speed, self.extent)
                before = self.positions[index]
                after = before + delta*self.directions[index]
                maximum = self.width()-self.extent-20
                if after > maximum or after < 142:
                    after = max(142., min(maximum, after))
                    self.directions[index] *= -1
                self.positions[index] = after
                pet.moved(after-before, self.extent)
            else:
                pet.time += dt
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor('#22232e' if self.dark else '#f4f1f8'))
        row_height = self.height()/5
        font = QtGui.QFont('Segoe UI', 11)
        painter.setFont(font)
        for index, (mascot, pet) in enumerate(zip(MASCOTS, self.pets)):
            ground = (index+1)*row_height-10
            painter.setPen(QtGui.QColor('#555869' if self.dark else '#cac2d4'))
            painter.drawLine(QtCore.QPointF(142, ground), QtCore.QPointF(self.width()-20, ground))
            for x in range(150, self.width()-20, 25):
                painter.drawLine(QtCore.QPointF(x, ground), QtCore.QPointF(x, ground+3))
            painter.setPen(QtGui.QColor('#eee8fa' if self.dark else '#362f40'))
            painter.drawText(QtCore.QRectF(18, index*row_height, 125, row_height),
                             QtCore.Qt.AlignVCenter, NAMES[index])
            _, action, expression = STATES[self.state]
            paint_pet(painter, QtCore.QRectF(self.positions[index], ground-self.extent*120/128,
                                            self.extent, self.extent), mascot,
                      phase=pet.phase, time=pet.time, action=action, expression=expression,
                      facing=self.directions[index], crawl_phase=pet.crawl_phase)


class Preview(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ClicknTranslate — маскоты · Python · кадры исходного GIF')
        self.resize(980, 740)
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel('Маскоты • визуальная доработка')
        title.setStyleSheet('font-size:18px;font-weight:600;')
        layout.addWidget(title)
        controls = QtWidgets.QHBoxLayout()
        self.scene = Scene()
        states = QtWidgets.QComboBox()
        states.addItems([s[0] for s in STATES])
        states.currentIndexChanged.connect(self.set_state)
        controls.addWidget(states)
        pause = QtWidgets.QCheckBox('Пауза')
        pause.toggled.connect(lambda value: setattr(self.scene, 'paused', value))
        controls.addWidget(pause)
        rate = QtWidgets.QComboBox()
        for text, value in (('1×', 1.), ('0.5×', .5), ('0.25×', .25)):
            rate.addItem(text, value)
        rate.currentIndexChanged.connect(lambda: setattr(self.scene, 'rate', rate.currentData()))
        controls.addWidget(rate)
        for label, attr, low, high, value in (('Скорость', 'speed', 20, 100, 40), ('Размер', 'extent', 60, 128, 128)):
            controls.addWidget(QtWidgets.QLabel(label))
            spin = QtWidgets.QSpinBox()
            spin.setRange(low, high)
            spin.setValue(value)
            spin.valueChanged.connect(lambda v, key=attr: self.set_value(key, v))
            controls.addWidget(spin)
        reset = QtWidgets.QPushButton('Сначала')
        reset.clicked.connect(self.scene.reset)
        controls.addWidget(reset)
        light = QtWidgets.QCheckBox('Светлый фон')
        light.toggled.connect(lambda value: self.set_value('dark', not value))
        controls.addWidget(light)
        layout.addLayout(controls)
        layout.addWidget(self.scene, 1)
        layout.addWidget(QtWidgets.QLabel('Выберите состояние. Пауза и замедление помогают рассмотреть лапки и ползание.'))
        self.setStyleSheet('''
            QWidget {background:#191a22;color:#eee8fa;font-family:"Segoe UI";font-size:13px;}
            QComboBox,QSpinBox,QPushButton {background:#303140;border:1px solid #5a526b;
                border-radius:5px;padding:6px;min-height:20px;}
            QPushButton:hover {background:#454057;}
        ''')

    def set_state(self, index):
        self.scene.state = index
        self.scene.update()

    def set_value(self, key, value):
        setattr(self.scene, key, value)
        self.scene.update()


def export(preview):
    """Render a visual draft for review, using the same scene as the live window."""
    from PIL import Image
    sys.path.insert(0, str(ROOT / 'tests'))
    from qt_layout_test_support import ensure_layout_fonts
    ensure_layout_fonts(QtWidgets.QApplication.instance())
    preview.scene.timer.stop()
    preview.show()
    QtWidgets.QApplication.processEvents()
    output = ROOT / 'docs/mascots'
    preview.grab().save(str(output / f'python-preview-{REVISION}.png'))
    poses = QtGui.QImage(100+150*len(WALK_FRAME_NAMES), 820, QtGui.QImage.Format_RGBA8888)
    poses.fill(QtGui.QColor('#22232e'))
    painter = QtGui.QPainter(poses)
    painter.setFont(QtGui.QFont('Segoe UI', 11))
    for row, mascot in enumerate(MASCOTS):
        painter.setPen(QtGui.QColor('#eee8fa'))
        painter.drawText(12, row*160+80, NAMES[row])
        for column, key in enumerate(WALK_FRAME_NAMES):
            x, y = 96+column*150, 8+row*160
            painter.setPen(QtGui.QColor('#555869'))
            painter.drawLine(x, y+120, x+140, y+120)
            phase = sum(WALK_FRAME_DURATIONS[:column])/sum(WALK_FRAME_DURATIONS) + 1e-7
            paint_pet(painter, QtCore.QRectF(x, y, 128, 128), mascot,
                      phase=phase, crawl_phase=phase, action='walk')
            painter.setPen(QtGui.QColor('#d5b3fc' if '-' in key else '#aaa4b4'))
            painter.drawText(x+48, y+144, key)
    painter.end()
    poses.save(str(output / f'walk-poses-{REVISION}.png'))
    frames = []
    for index in range(400):
        if index == 200:
            preview.scene.directions = [-1] * 5
        preview.scene.advance(.02)
        canvas = preview.scene.grab().toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
        pointer = canvas.bits()
        pointer.setsize(canvas.byteCount())
        frame = Image.frombytes('RGBA', (canvas.width(), canvas.height()), bytes(pointer)).convert('RGB')
        frames.append(frame)
        if index in (0, 4, 8, 12, 16, 24, 40, 60, 99, 145):
            frame.save(output / f'{REVISION}-phase-{index:03}.png')
    palette_sheet = Image.new('RGB', (frames[0].width*4, frames[0].height))
    for slot, index in enumerate((0, 100, 200, 300)):
        palette_sheet.paste(frames[index], (slot*frames[0].width, 0))
    palette = palette_sheet.quantize(colors=256)
    encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    encoded[0].save(output / f'motion-{REVISION}.gif', save_all=True, append_images=encoded[1:], duration=20, loop=0)
    print(output / f'motion-{REVISION}.gif')


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    preview = Preview()
    if '--export' in sys.argv:
        export(preview)
    else:
        preview.show()
        sys.exit(app.exec_())
