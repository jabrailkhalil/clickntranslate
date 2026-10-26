"""Reflow OCR text before translation, without a language model or extra requests.

Geometry is in capture pixels, so all thresholds scale with text height. Separate
columns and visible paragraph gaps remain separate translation blocks.
"""
import math
import re


_LIST_START = re.compile(r'^\s*(?:[-*•●▪‣–—]|\d+[.)]|[A-Za-z][.)])\s+')
_PARAGRAPH_BREAK = re.compile(r'\n[ \t]*\n+')


def _join(left, right):
    if not left:
        return right
    if not right:
        return left
    # A soft hyphen explicitly marks a discretionary word break. Do not guess
    # whether a visible hyphen is part of a word such as "cross-reference".
    if left.endswith('\u00ad'):
        return left[:-1] + right
    if len(left)>1 and left.endswith(('-', '\u2010')) and left[-2].isalpha() and right[0].isalpha():
        return left + right
    cjk = lambda c: '\u3400' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff'
    return left + ('' if cjk(left[-1]) and cjk(right[0]) else ' ') + right


def merge_text_lines(text):
    """Fallback when boxes are unavailable; retain blank lines and list items."""
    text = str(text or '').replace('\r\n', '\n').replace('\r', '\n')
    paragraphs = []
    for section in _PARAGRAPH_BREAK.split(text.strip()):
        current = ''
        for line in section.splitlines():
            line = line.strip()
            if not line:
                continue
            if current and _LIST_START.match(line):
                paragraphs.append(current)
                current = ''
            current = _join(current, line)
        if current:
            paragraphs.append(current)
    return '\n\n'.join(paragraphs)


def boxes_from_items(items):
    rows = []
    for box, text, _confidence in items or []:
        try:
            xs, ys = [float(p[0]) for p in box], [float(p[1]) for p in box]
            rows.append((min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys), text))
        except (TypeError, ValueError, IndexError):
            # Unknown geometry is kept as its own block, never dropped.
            rows.append((None, None, None, None, text))
    return rows


def _valid_rows(rows):
    valid, unknown = [], []
    for item in rows or []:
        if not isinstance(item, (tuple, list)) or len(item) < 5:
            continue
        text = str(item[4] or '').strip()
        if not text:
            continue
        try:
            x, y, w, h = map(float, item[:4])
            if not all(map(math.isfinite, (x, y, w, h))) or w <= 0 or h <= 0:
                raise ValueError('Invalid OCR bounds')
            valid.append((x, y, w, h, text))
        except (TypeError, ValueError):
            unknown.append(text)
    return valid, unknown


def _union(rows, text):
    left, top = min(r[0] for r in rows), min(r[1] for r in rows)
    right, bottom = max(r[0]+r[2] for r in rows), max(r[1]+r[3] for r in rows)
    return left, top, right-left, bottom-top, text


def _visual_rows(rows):
    """Join adjacent word fragments, leaving a column gutter untouched."""
    from ocr_text_layout import ocr_visual_lines, inline_reading_order
    # Group baselines first, then traverse by x. Sorting by the tops of tilted
    # word boxes used to leave two disconnected fragments when the bridging
    # word arrived later, and the paragraph reader mistook them for columns.
    items = [([[x,y],[x+w,y],[x+w,y+h],[x,y+h]], text, row)
             for row in rows for x,y,w,h,text in (row,)]
    groups=[]
    for visual_line in ocr_visual_lines(items):
        current=[]
        right=None
        previous_height=0
        for item in visual_line:
            row=item[2]
            x,y,w,h,_text=row
            if current and x-right > .9*max(h,previous_height):
                groups.append(current)
                current=[]
            current.append(row)
            right=max(right if right is not None else x,x+w)
            previous_height=h
        if current:
            groups.append(current)
    result=[]
    for group in groups:
        ordered = inline_reading_order(group, position=lambda row: row[0], text=lambda row: row[4])
        text=' '.join(r[4] for r in ordered)
        result.append(_union(group,text))
    return sorted(result,key=lambda r:(r[1],r[0]))


def _reading_order(blocks):
    """Read columns top-to-bottom, with separate horizontal bands for headings."""
    if len(blocks) < 2:
        return blocks
    for axis, extent in ((0,2),(1,3)):
        groups=[]
        edge=None
        for block in sorted(blocks,key=lambda b:b[axis]):
            start, end=block[axis],block[axis]+block[extent]
            if edge is None or start > edge:
                groups.append([])
            groups[-1].append(block)
            edge=max(edge if edge is not None else end,end)
        if len(groups)>1:
            return [block for group in groups for block in _reading_order(group)]
    return sorted(blocks,key=lambda b:(b[1],b[0]))


def paragraph_blocks(rows):
    """Return positioned paragraphs as (x, y, width, height, text) tuples."""
    positioned, unknown = _valid_rows(rows)
    lines = _visual_rows(positioned)
    groups=[]
    active=[]
    for row in lines:
        x,y,w,h,text=row
        best=None
        best_cost=None
        active=[group for group in active if group[-1][1]+1.85*group[-1][3]>=y]
        for group in active:
            previous=group[-1]
            px,py,pw,ph,pt=previous
            typical=ph
            gap=y-(py+ph)
            overlap=min(x+w,px+pw)-max(x,px)
            aligned=min(abs(x-px),abs(x+w-px-pw)) <= .85*typical
            # A first-line indent can differ from the rest of its paragraph.
            indent=len(group)==1 and abs(x-px)<=2*typical and overlap>=.6*min(w,pw)
            if (gap < -.15*min(h,ph) or gap > .85*typical
                    or max(h,typical)>1.5*min(h,typical)
                    or overlap < .25*min(w,pw) or not (aligned or indent)
                    or _LIST_START.match(text)):
                continue
            cost=abs(gap)+min(abs(x-px),abs(x+w-px-pw))
            if best_cost is None or cost<best_cost:
                best,best_cost=group,cost
        if best is None:
            group=[row]
            groups.append(group)
            active.append(group)
        else:
            best.append(row)
    paragraphs=[]
    for group in groups:
        text=''
        for row in group:
            text=_join(text,row[4])
        paragraphs.append(_union(group,text))
    # Unknown boxes cannot be positioned as overlays, but their text is retained
    # by paragraph_text instead of being silently lost.
    return _reading_order(paragraphs)


def paragraph_text(rows):
    positioned, unknown=_valid_rows(rows)
    return '\n\n'.join([block[4] for block in paragraph_blocks(positioned)] + unknown)


def tesseract_items(data):
    """Retain native lines without bridging two distant PSM 6 columns.

    Tesseract already knows which short Arabic words share a baseline. Treating
    each word as an independent box can misread wide word spaces as columns.
    Preserve that line identity and its logical word order, splitting only a
    genuine gutter before passing the chunks to the paragraph reader.
    """
    items=[]
    lines={}
    line_columns = ('page_num', 'block_num', 'par_num', 'line_num')
    has_lines = all(len(data.get(name, [])) == len(data.get('text', [])) for name in line_columns)
    for i,value in enumerate(data.get('text', [])):
        text=str(value or '').strip()
        if not text:
            continue
        x,y,w,h=(float(data[name][i]) for name in ('left','top','width','height'))
        if has_lines:
            key=tuple(data[name][i] for name in line_columns)
            lines.setdefault(key, []).append((x,y,w,h,text,i))
        else:
            items.append(([[x,y],[x+w,y],[x+w,y+h],[x,y+h]],text,0.0))
    for words in lines.values():
        line_height=max(row[1]+row[3] for row in words)-min(row[1] for row in words)
        chunks=[]
        edge=None
        for word in sorted(words, key=lambda row:row[0]):
            if edge is None or word[0]-edge > 2*line_height:
                chunks.append([])
            chunks[-1].append(word)
            edge=max(edge if edge is not None else word[0],word[0]+word[2])
        for chunk in chunks:
            text=' '.join(word[4] for word in sorted(chunk,key=lambda row:row[5]))
            x,y,w,h,_text=_union(chunk,text)
            items.append(([[x,y],[x+w,y],[x+w,y+h],[x,y+h]],text,0.0))
    return items
