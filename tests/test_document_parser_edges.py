"""Import boundaries and declared encodings from ordinary HTML documents."""
import codecs
import zipfile

import pytest

from document_parser import parse_document


@pytest.mark.parametrize('encoding,phrase,declaration', [
    ('cp1252', 'Français : café, élève', '<meta charset="windows-1252">'),
    ('cp1256', 'مرحبا بالعالم', '<META CHARSET = "windows-1256">'),
    ('cp932', '日本語の文書', '<meta http-equiv="Content-Type" content="text/html; charset=Shift_JIS">'),
])
def test_html_declared_encoding_preserves_source_characters(tmp_path, encoding, phrase, declaration):
    path = tmp_path / 'document.html'
    path.write_bytes(('<html><head>' + declaration + '</head><body><p>' + phrase +
                      '</p></body></html>').encode(encoding))
    assert parse_document(path).text == phrase


@pytest.mark.parametrize('encoding,bom', [('utf-8', codecs.BOM_UTF8),
                                         ('utf-16-le', codecs.BOM_UTF16_LE),
                                         ('utf-32-be', codecs.BOM_UTF32_BE)])
def test_html_bom_takes_precedence_over_a_stale_charset(tmp_path, encoding, bom):
    path = tmp_path / 'document.htm'
    phrase = 'مرحبا — café — 日本語'
    html = '<meta charset="windows-1252"><p>' + phrase + '</p>'
    path.write_bytes(bom + html.encode(encoding))
    assert parse_document(path).text == phrase


def test_html_unknown_charset_keeps_existing_unicode_fallback(tmp_path):
    path = tmp_path / 'document.html'
    path.write_text('<meta charset="not-a-codec"><p>مرحبا &amp; café</p>', encoding='utf-8')
    assert parse_document(path).text == 'مرحبا & café'


def test_html_table_cells_never_merge_distinct_words_or_values(tmp_path):
    path = tmp_path / 'table.html'
    path.write_text('<table><tr><th>Product</th><th>Count</th></tr>'
                    '<tr><td>USB cable</td><td>12</td></tr></table>', encoding='utf-8')
    text = parse_document(path).text
    assert text.split() == ['Product', 'Count', 'USB', 'cable', '12']
    assert text.index('\n') < text.index('USB cable')


@pytest.mark.parametrize('shape', [
    '<w:pict><v:shape><v:textbox>{content}</v:textbox></v:shape></w:pict>',
    '<w:drawing><a:graphic><a:graphicData><wps:wsp><wps:txbx>{content}'
    '</wps:txbx></wps:wsp></a:graphicData></a:graphic></w:drawing>',
])
def test_docx_textbox_is_a_single_separate_paragraph(tmp_path, shape):
    textbox = '<w:txbxContent><w:p><w:r><w:t>Inside box</w:t></w:r></w:p></w:txbxContent>'
    xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
           'xmlns:v="urn:schemas-microsoft-com:vml" '
           'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
           'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
           '<w:body><w:p><w:r><w:t>Main paragraph.</w:t></w:r><w:r>' +
           shape.format(content=textbox) + '</w:r></w:p><w:p><w:r><w:t>Next paragraph.</w:t>'
           '</w:r></w:p></w:body></w:document>')
    path = tmp_path / 'textbox.docx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    assert parse_document(path).text == 'Main paragraph.\n\nInside box\n\nNext paragraph.'


@pytest.mark.parametrize('tag', ['br', 'hr'])
@pytest.mark.parametrize('count', [1, 2, 3])
def test_html_void_element_syntax_does_not_change_text_boundaries(tmp_path, tag, count):
    plain = tmp_path / 'plain.html'
    closed = tmp_path / 'self_closed.html'
    plain.write_text('<p>First' + f'<{tag}>' * count + 'Second</p>', encoding='utf-8')
    closed.write_text('<p>First' + f'<{tag}/>' * count + 'Second</p>', encoding='utf-8')
    expected = 'First' + '\n' * count + 'Second'
    assert parse_document(plain).text == expected
    assert parse_document(closed).text == expected


@pytest.mark.parametrize('empty_tag', ['script', 'style'])
def test_empty_self_closed_raw_text_element_does_not_hide_the_following_body(tmp_path, empty_tag):
    path = tmp_path / 'empty.html'
    path.write_text(f'<{empty_tag}/><p>Visible source</p>', encoding='utf-8')
    assert parse_document(path).text == 'Visible source'


@pytest.mark.parametrize('control,expected', [
    ('cr', 'First\nSecond'), ('noBreakHyphen', 'First-Second'),
    ('br', 'First\nSecond'), ('tab', 'First\tSecond'),
])
def test_docx_run_control_preserves_its_plain_text_content(tmp_path, control, expected):
    xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:p><w:r><w:t>First</w:t><w:' + control + '/><w:t>Second</w:t>'
           '</w:r></w:p></w:body></w:document>')
    path = tmp_path / 'run-controls.docx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    assert parse_document(path).text == expected


@pytest.mark.parametrize('markup,expected', [
    ('<p>Contact AT&T', 'Contact AT&T'),
    ('<div>Compare A &amp', 'Compare A &'),
    ('<p>Prefix <', 'Prefix <'),
])
def test_html_end_of_file_flushes_the_last_paragraph(tmp_path, markup, expected):
    path = tmp_path / 'last-paragraph.html'
    path.write_text(markup, encoding='utf-8')
    assert parse_document(path).text == expected


def test_word_strict_ooxml_uses_its_own_paragraph_and_run_namespace(tmp_path):
    xml = ('<w:document xmlns:w="http://purl.oclc.org/ooxml/wordprocessingml/main">'
           '<w:body><w:p><w:r><w:t>Strict документ</w:t><w:tab/><w:t>مرحبا</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>Next paragraph</w:t></w:r></w:p></w:body></w:document>')
    path = tmp_path / 'strict.docx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    assert parse_document(path).text == 'Strict документ\tمرحبا\n\nNext paragraph'


@pytest.mark.parametrize('readable_choice', [True, False])
def test_docx_chooses_a_single_readable_textbox_representation(tmp_path, readable_choice):
    def paragraph(text):
        return '<w:p><w:r><w:t>' + text + '</w:t></w:r></w:p>'

    choice = '<w:txbxContent>' + paragraph('Current caption') + '</w:txbxContent>' if readable_choice else ''
    fallback = '<w:txbxContent>' + paragraph('Legacy caption') + '</w:txbxContent>'
    xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
           'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
           'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
           'xmlns:v="urn:schemas-microsoft-com:vml"><w:body>' + paragraph('Total') +
           '<w:p><w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wps:wsp><wps:txbx>' +
           choice + '</wps:txbx></wps:wsp></w:drawing></mc:Choice><mc:Fallback><w:pict><v:shape><v:textbox>' +
           fallback + '</v:textbox></v:shape></w:pict></mc:Fallback></mc:AlternateContent></w:r></w:p>' +
           paragraph('Total') + '</w:body></w:document>')
    path = tmp_path / 'textbox-compatibility.docx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    caption = 'Current caption' if readable_choice else 'Legacy caption'
    assert parse_document(path).text == 'Total\n\n' + caption + '\n\nTotal'


def test_rtf_uses_the_unicode_field_result_instead_of_its_ansi_compatibility_copy(tmp_path):
    path = tmp_path / 'arabic-reference.rtf'
    path.write_bytes(
        rb'{\rtf1\ansi\ansicpg1252 Before {\field{\*\fldinst REF cities}'
        rb'{\upr{\fldrslt City ???}{\*\ud{\fldrslt City \u1576?\u1594?\u1583?\u1575?\u1583?}}}} after}')
    assert parse_document(path).text == 'Before City بغداد after'


def test_rtf_unicode_alternatives_stay_inside_their_own_destination(tmp_path):
    path = tmp_path / 'nested-references.rtf'
    path.write_bytes(
        rb'{\rtf1\ansi Prefix {\upr{outer ANSI}{\*\ud{Outer {\upr{inner ANSI}{\*\ud \u945?}} end}}} '
        rb'{\upr{kept ANSI}}{\*\metadata {\upr{discarded ANSI}{\*\ud hidden}}}{\*\ud hidden} tail}')
    assert parse_document(path).text == 'Prefix Outer α end kept ANSI tail'
