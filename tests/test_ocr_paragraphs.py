"""Wrapped game text must reach the translator as paragraphs, for any target."""
from types import SimpleNamespace
from unittest import mock

import pytest
import ocr
from ocr_paragraphs import merge_text_lines, paragraph_blocks, paragraph_text
from ocr_text_layout import ocr_text_from_items


REPORTED_LINES = [
    'have solved the secret of the', 'ancient Nistrian alphabet. A',
    'large portion of my records', 'seems to describe some rather',
    'fascinating magic rituals and', 'practices that are only briefly',
    'mentioned in ancient', 'chronicles... Once I get home,',
    'taking a trip to Maen is the first', "order of business. I'm certain",
    'these findings will greatly', 'interest the Academy...',
]


def rows(texts, x=10, y=10, width=400, height=26, pitch=38):
    return [(x,y+i*pitch,width,height,text) for i,text in enumerate(texts)]


def items(rectangles):
    return [([[x,y],[x+w,y],[x+w,y+h],[x,y+h]],text,.99)
            for x,y,w,h,text in rectangles]


def test_reported_twelve_lines_become_exactly_the_users_corrected_paragraph():
    source='\r\n'.join(REPORTED_LINES)
    expected=' '.join(REPORTED_LINES)
    assert merge_text_lines(source)==expected
    assert paragraph_text(rows(REPORTED_LINES))==expected
    assert len(expected.split())==57
    assert ocr_text_from_items(items(rows(REPORTED_LINES)))=='\n'.join(REPORTED_LINES)
    assert ocr_text_from_items(items(rows(REPORTED_LINES)),join_paragraphs=True)==expected


def test_real_paragraph_gaps_and_two_book_pages_keep_their_reading_order():
    rectangles=(rows(['Left page first','paragraph continues.'])
                +rows(['Left page second','paragraph continues.'],y=160)
                +rows(['Right page first','paragraph continues.'],x=600))
    assert paragraph_text(rectangles)==('Left page first paragraph continues.\n\n'
                                       'Left page second paragraph continues.\n\n'
                                       'Right page first paragraph continues.')
    blocks=paragraph_blocks(rectangles)
    assert len(blocks)==3
    assert all(w<500 for x,y,w,h,text in blocks)


def test_list_items_and_blank_lines_are_not_flattened():
    assert merge_text_lines('A wrapped\nparagraph.\n\n1. First item\ncontinues\n2. Second item')==(
        'A wrapped paragraph.\n\n1. First item continues\n\n2. Second item')
    blocks=paragraph_blocks(rows(['1. First item','continues','2. Second item']))
    assert [b[4] for b in blocks]==['1. First item continues','2. Second item']


def test_cjk_soft_hyphens_and_unknown_boxes_do_not_lose_text():
    assert merge_text_lines('日本語\n文章')=='日本語文章'
    assert merge_text_lines('trans\u00ad\nlation')=='translation'
    assert merge_text_lines('cross-\nreference')=='cross-reference'
    assert paragraph_text([(None,None,None,None,'Unpositioned text')])=='Unpositioned text'
    assert paragraph_text([None,(),(0,0,float('nan'),10,'Invalid bounds')])=='Invalid bounds'


@pytest.mark.parametrize('enabled',[False,True])
def test_windows_ocr_uses_line_geometry_before_translating(enabled):
    lines=[]
    for x,y,w,h,text in rows(REPORTED_LINES):
        word=SimpleNamespace(text=text,bounding_rect=SimpleNamespace(x=x,y=y,width=w,height=h))
        lines.append(SimpleNamespace(text=text,words=[word]))
    result=SimpleNamespace(lines=lines)
    expected=(' ' if enabled else '\n').join(REPORTED_LINES)
    assert ocr.OCRWorker._extract_result_text(result,join_paragraphs=enabled)==expected
    assert ocr._windows_ocr_result_to_text(result,join_paragraphs=enabled)==expected


def test_fullscreen_overlay_groups_paragraphs_only_when_enabled():
    source=rows(REPORTED_LINES)
    assert len(ocr._group_screen_ocr_lines(source))==12
    assert [b[4] for b in ocr._group_screen_ocr_lines(source,join_paragraphs=True)]==[' '.join(REPORTED_LINES)]


@pytest.mark.parametrize('mode',['translate','copy'])
@pytest.mark.parametrize('enabled',[False,True])
def test_area_worker_applies_paragraph_setting_to_translation_only(mode,enabled):
    owner=SimpleNamespace(mode=mode,_set_ocr_status_text=mock.Mock(),handle_ocr_result=mock.Mock())
    with mock.patch.object(ocr,'get_cached_ocr_config',return_value={'ocr_join_paragraphs':enabled}), \
            mock.patch.object(ocr,'RapidOCRWorker') as factory:
        ocr.ScreenCaptureOverlay._start_rapidocr_worker(owner,[], 'primary','test')
        assert factory.return_value.join_paragraphs==(enabled and mode=='translate')
        factory.return_value.start.assert_called_once()


@pytest.mark.parametrize('engine',['rapidocr','easyocr'])
def test_isolated_ocr_worker_keeps_geometry_for_the_same_pretranslation_step(engine):
    rectangles=rows(REPORTED_LINES)
    response={'results':[{'label':'raw','text':'\n'.join(REPORTED_LINES),'items':items(rectangles),'confidence':.99,'boxes_count':12}]}
    with mock.patch.object(ocr,'_call_native_ocr_worker',return_value=response):
        result,_=ocr._recognize_with_native_ocr_worker(engine,[], 'primary','test',join_paragraphs=True)
    assert result==' '.join(REPORTED_LINES)


def test_tesseract_uses_positioned_words_for_paragraphs_instead_of_mixing_columns():
    import pytesseract
    from PIL import Image
    rectangles = rows(REPORTED_LINES)
    data = {name: [row[index] for row in rectangles]
            for index, name in enumerate(('left', 'top', 'width', 'height', 'text'))}
    with mock.patch.object(ocr, '_tesseract_psm_order', return_value=[6]), \
         mock.patch.object(pytesseract, 'image_to_data', return_value=data) as recognize, \
         mock.patch.object(pytesseract, 'image_to_string') as plain:
        text = ocr._run_tesseract_ocr_image_with_cmd(
            Image.new('RGB', (500, 500)), 'tesseract', 'eng', 'test', 'test', join_paragraphs=True)
    assert text == ' '.join(REPORTED_LINES)
    recognize.assert_called_once()
    plain.assert_not_called()


def test_dynamic_translation_keeps_paragraph_breaks_after_normalization():
    from game_mode import normalize_game_ocr_text
    assert normalize_game_ocr_text('First paragraph\ncontinues.\n\nSecond paragraph.', join_paragraphs=True) == (
        'First paragraph continues.\n\nSecond paragraph.')
