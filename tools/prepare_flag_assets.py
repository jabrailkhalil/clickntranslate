"""Maintain the bundled vector flags; never run a download from the application."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import sys
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from extended_languages import EXTRA_FLAG_COUNTRIES

VERSION = 'v7.3.2'
UPSTREAM = f'https://raw.githubusercontent.com/lipis/flag-icons/{VERSION}'
COUNTRIES = set(EXTRA_FLAG_COUNTRIES.values()) | {
    'us', 'ru', 'de', 'fr', 'es', 'it', 'pt', 'pl', 'ua', 'tr', 'nl', 'cn', 'jp', 'kr', 'sa', 'in'}
SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')


def download(path):
    request = Request(UPSTREAM+'/'+path, headers={'User-Agent': 'ClicknTranslate-asset-preparation'})
    with urlopen(request, timeout=30) as response:
        content = response.read(2*1024*1024+1)
    if len(content) > 2*1024*1024:
        raise ValueError('Unexpectedly large flag asset: '+path)
    return content


def framed_flag(content):
    flag = ET.fromstring(content)
    if flag.tag != f'{{{SVG}}}svg' or 'viewBox' not in flag.attrib:
        raise ValueError('A vector flag with a viewBox is required')
    markers = [element for element in flag if element.tag == f'{{{SVG}}}marker']
    if markers:
        if flag.get('id') != 'flag-icons-us' or len(markers) != 1:
            raise ValueError('Review SVG markers unsupported by QtSvg 5')
        for element in list(flag):
            if element.tag == f'{{{SVG}}}marker' or 'marker-mid' in element.attrib:
                flag.remove(element)
        # Expand the US flag's unsupported marker into its fifty ordinary paths.
        # QtSvg 5 otherwise silently drops the repeated stars.
        stars = ET.SubElement(flag, f'{{{SVG}}}g', fill='#fff')
        for row in range(9):
            for column in range(6 if row % 2 == 0 else 5):
                cx = (30.4 if row % 2 == 0 else 60.8)+60.8*column
                cy = 25.85*(row+1)
                points = []
                for point in range(10):
                    radius = 14 if point % 2 == 0 else 5.3475
                    angle = -math.pi/2+point*math.pi/5
                    points.append(f'{cx+radius*math.cos(angle):.5f},{cy+radius*math.sin(angle):.5f}')
                ET.SubElement(stars, f'{{{SVG}}}polygon', points=' '.join(points))
    for element in flag.iter():
        if element.tag.rsplit('}', 1)[-1] in {'script', 'image', 'foreignObject'}:
            raise ValueError('Flags must be self-contained vector drawings')
        for name, value in element.attrib.items():
            if name.rsplit('}', 1)[-1] == 'href' and not value.startswith('#'):
                raise ValueError('External flag references are forbidden')
        # QtSvg 5 implements SVG 1.1 references, not the SVG 2 href shorthand.
        if 'href' in element.attrib:
            element.set('{http://www.w3.org/1999/xlink}href', element.attrib.pop('href'))
    root = ET.Element(f'{{{SVG}}}svg', viewBox='0 0 90 80', width='90', height='80')
    defs = ET.SubElement(root, f'{{{SVG}}}defs')
    clip = ET.SubElement(defs, f'{{{SVG}}}clipPath', id='cnt-flag-shape')
    ET.SubElement(clip, f'{{{SVG}}}rect', x='6', y='10', width='78', height='60', rx='8')
    ET.SubElement(root, f'{{{SVG}}}rect', x='2', y='6', width='86', height='68', rx='12', fill='#fff')
    group = ET.SubElement(root, f'{{{SVG}}}g', {'clip-path': 'url(#cnt-flag-shape)'})
    # Flatten the source viewBox instead of nesting another <svg>. QtSvg 5
    # does not consistently apply nested viewport clipping and sizing.
    x, y, width, height = map(float, flag.attrib['viewBox'].replace(',', ' ').split())
    attributes = {name: value for name, value in flag.attrib.items()
                  if name not in ('viewBox', 'width', 'height', 'x', 'y', 'version')}
    attributes['transform'] = f'translate(6 10) scale({78/width:.12g} {60/height:.12g}) translate({-x:g} {-y:g})'
    drawing = ET.SubElement(group, f'{{{SVG}}}g', attributes)
    drawing.extend(flag)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)+b'\n'


def main():
    destination = ROOT/'src/icons/flags'
    destination.mkdir(exist_ok=True)
    def prepare(country):
        original = download(f'flags/4x3/{country}.svg')
        rendered = framed_flag(original)
        (destination/(country+'.svg')).write_bytes(rendered)
        return country, {'upstream_sha256': hashlib.sha256(original).hexdigest(),
                         'bundled_sha256': hashlib.sha256(rendered).hexdigest()}
    with ThreadPoolExecutor(max_workers=4) as pool:
        files = dict(pool.map(prepare, sorted(COUNTRIES)))
    license_text = download('LICENSE')
    if b'Copyright (c) 2013 Panayiotis Lipiridis' not in license_text:
        raise ValueError('Review the changed upstream license before updating flags')
    (destination/'LICENSE.txt').write_bytes(license_text)
    (destination/'vector-sources.json').write_text(json.dumps(dict(source=UPSTREAM, license='MIT',
        adaptation='Rounded white frame; QtSvg 5 compatible references; US marker stars expanded into 50 vector polygons.',
        files=files), indent=2)+'\n', encoding='utf-8')
    print(f'Prepared {len(files)} self-contained vector flags with their license.')


if __name__ == '__main__':
    main()
