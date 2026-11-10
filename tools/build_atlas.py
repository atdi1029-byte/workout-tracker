#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Builds atlas/atlas.json and atlas/img/ from the Exercise Atlas book.

The app's "Atlas" button on each lift shows that lift's entry from the Exercise Atlas
(Books/exercise-atlas/index.html): what it hits, why it is in the program, what to swap
it with, what to watch, and the anatomy plate. This script turns the book page into one
JSON file keyed the same way the app keys exercises (exId), and copies the plates.

Run it again whenever the atlas changes:
    /usr/bin/python3 tools/build_atlas.py
then bump the service worker cache version.
"""
import html
import json
import os
import re
import shutil
import unicodedata

SRC = '/Users/alexbarnett/Books/exercise-atlas'
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'atlas'))
STAT_RE = re.compile(r'programs?\b|sessions?\b|working sets|\btop \d|^(core|regular|rare|one-off|occasional)$', re.I)


def ex_id(name):
    """Same as exId() in index.html."""
    s = unicodedata.normalize('NFD', name.lower())
    s = ''.join(c for c in s if not ('̀' <= c <= 'ͯ'))
    s = s.replace('(', 'p_').replace(')', '_p')
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return re.sub(r'^_|_$', '', s)


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()


def clean_html(s):
    """Keep paragraphs, bold labels and emphasis; drop everything else."""
    s = re.sub(r'\s+', ' ', s or '')
    s = re.sub(r'<(?!/?(p|b|em|i|strong)\b)[^>]*>', '', s)
    s = re.sub(r'<p\b[^>]*>', '<p>', s)
    s = re.sub(r'<(em|i|strong)\b[^>]*>', r'<\1>', s)
    s = re.sub(r'<b\b(?: class="(hits|purp|swap|watch)")?[^>]*>', lambda m: '<b class="%s">' % m.group(1) if m.group(1) else '<b>', s)
    return s.strip()


def main():
    page = open(os.path.join(SRC, 'index.html'), encoding='utf-8').read()
    sections = [(m.start(), text(m.group(2))) for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', page, flags=re.S)]

    def section_at(pos):
        name = ''
        for p, label in sections:
            if p <= pos:
                name = label
        return re.sub(r'^\d+\.\s*', '', name)

    entries, order, images = {}, [], set()
    for m in re.finditer(r'<article class="entry" id="([^"]+)">(.*?)</article>', page, flags=re.S):
        body = m.group(2)
        h3 = re.search(r'<h3>(.*?)</h3>', body, flags=re.S)
        if not h3:
            continue
        pt = re.search(r'<span class="pt">(.*?)</span>', h3.group(1), flags=re.S)
        en = text(re.sub(r'<span class="pt">.*?</span>', '', h3.group(1), flags=re.S))
        ptn = text(pt.group(1)) if pt else en
        meta = re.search(r'<p class="meta">(.*?)</p>', body, flags=re.S)
        segs = [text(x) for x in re.split(r'&middot;|·', meta.group(1))] if meta else []
        segs = [x for x in segs if x and not STAT_RE.search(x)]
        txt = re.search(r'<div class="txt">(.*?)</div>\s*<div class="fig">', body, flags=re.S)
        fig = re.search(r'<div class="fig">(.*?)</div>\s*</div>', body, flags=re.S)
        img = re.search(r'src="img/([^"]+)"', fig.group(1)) if fig else None
        cap = re.search(r'<p class="mcap">\s*<b>(.*?)</b>', fig.group(1), flags=re.S) if fig else None
        e = {
            'en': en, 'pt': ptn, 'section': section_at(m.start()),
            'hits': segs[0] if len(segs) > 0 else '',
            'also': segs[1] if len(segs) > 1 else '',
            'pattern': segs[2] if len(segs) > 2 else '',
            'html': clean_html(txt.group(1)) if txt else '',
            'img': img.group(1) if img else '',
            'plate': text(cap.group(1)) if cap else '',
        }
        if e['img']:
            images.add(e['img'])
        key = ex_id(ptn)
        entries[key] = e
        order.append(key)
    alias = {}
    for key in order:
        k2 = ex_id(entries[key]['en'])
        if k2 and k2 != key and k2 not in entries and k2 not in alias:
            alias[k2] = key

    muscles = {}
    for m in re.finditer(r'<figure id="mu-([^"]+)">(.*?)</figure>', page, flags=re.S):
        src = re.search(r'src="img/([^"]+)"', m.group(2))
        cap = re.search(r'<figcaption>(.*?)</figcaption>', m.group(2), flags=re.S)
        reg = re.search(r'<span class="reg">(.*?)</span>', cap.group(1), flags=re.S) if cap else None
        nm = re.search(r'<b>(.*?)</b>', cap.group(1), flags=re.S) if cap else None
        rest = re.sub(r'<span class="reg">.*?</span>|<b>.*?</b>', '', cap.group(1), flags=re.S) if cap else ''
        if src:
            images.add(src.group(1))
            muscles[src.group(1)] = {'name': text(nm.group(1)) if nm else '', 'region': text(reg.group(1)) if reg else '', 'text': text(rest)}

    credits = {}
    for c in json.load(open(os.path.join(SRC, 'img', 'credits.json'), encoding='utf-8')):
        credits[c['file']] = {'title': c.get('title', ''), 'artist': c.get('artist', ''), 'license': c.get('license', ''), 'source': c.get('source', '')}

    os.makedirs(os.path.join(OUT, 'img'), exist_ok=True)
    for f in sorted(images):
        shutil.copyfile(os.path.join(SRC, 'img', f), os.path.join(OUT, 'img', f))
    out = {'v': 1, 'entries': entries, 'alias': alias, 'muscles': muscles, 'credits': credits}
    with open(os.path.join(OUT, 'atlas.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    size = os.path.getsize(os.path.join(OUT, 'atlas.json'))
    print('%d entries, %d aliases, %d plates, atlas.json %d bytes' % (len(entries), len(alias), len(images), size))
    return out


if __name__ == '__main__':
    main()
