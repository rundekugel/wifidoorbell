#!/usr/bin/env python3
"""
Decoder fuer Ritto-2-Draht-Mitschnitte aus Saleae Logic 2 (.sal).

- liest das interne .sal-Digitalformat direkt (inoffiziell, reverse-engineered,
  getestet mit .sal-Version 14 / Logic 2 von 2021; kann sich in neueren
  Versionen aendern)
- erkennt Telegramme, bildet die Huellkurve der ~16-kHz-Traegerbursts
- klassifiziert Bursts als kurz (S) / lang (L), Gruppen je 9 Symbole
- gibt 8 Datenbits + Paritaetsbit je Gruppe aus

Aufruf: python3 ritto_sal_decode.py capture.sal [kanal]
Die .sal-Datei wird nur gelesen, nicht veraendert.
"""
import re, struct, sys, zipfile, json

# --- .sal-Digitalformat -------------------------------------------------
REC = re.compile(re.escape(bytes.fromhex('e0030000000000001bb7000000000001')))

def rle(payload):
    """Laengen der Laeufe. Erstes Byte: Bit6 = weitere Bytes folgen,
    Bits5..0 Wert; Folgebytes: Bit7 = weitere folgen, Bits6..0 Wert.
    Big-Endian, gespeichert als (Laenge - 1)."""
    out, i = [], 0
    while i < len(payload):
        c = payload[i]; i += 1
        x, more = c & 0x3F, c & 0x40
        while more:
            c = payload[i]; i += 1
            x, more = (x << 7) | (c & 0x7F), c & 0x80
        out.append(x + 1)
    return out

def edges_from_sal(path, ch=0):
    z = zipfile.ZipFile(path)
    meta = json.loads(z.read('meta.json'))
    m = re.search(r'"sampleRate":\s*\{"digital":\s*(\d+)', json.dumps(meta))
    fs = float(m.group(1)) if m else 12e6
    b = z.read(f'digital-{ch}.bin')
    edges, prev = [], None
    for m in REC.finditer(b):
        p = m.start()
        start = struct.unpack('<Q', b[p-16:p-8])[0] * 256   # Blockeinheit = 256 Samples
        ln = struct.unpack('<Q', b[p+23:p+31])[0]
        q = p + 31 + ln
        st = struct.unpack('<i', b[q+24:q+28])[0]           # Pegel am Blockanfang
        runs = rle(b[p+31:q])
        s = start
        if prev is not None and st != prev:
            edges.append((s, st))
        cur = st
        for r in runs[:-1]:
            s += r; cur ^= 1; edges.append((s, cur))
        prev = cur
    return [(s / fs, lvl) for s, lvl in edges], fs

# --- Telegramm-Analyse ---------------------------------------------------
def split(times, gap):
    groups = [[times[0]]]
    for x in times[1:]:
        (groups[-1].append(x) if x - groups[-1][-1] < gap else groups.append([x]))
    return groups

def is_long(g, part):
    if part == 0:                       # Teil 1: Burstdauer kurz ~125 us / lang ~375 us
        return g[-1] - g[0] > 250e-6
    fast = sum(1 for a, b in zip(g, g[1:]) if b - a < 90e-6)
    return fast >= 6                    # Teil 2: 8 schnelle Spikes vs. 4 schnelle + 3 langsame

def decode_part(bursts, part):
    syms, cur = [], ''
    for j, g in enumerate(bursts):
        cur += 'L' if is_long(g, part) else 'S'
        per = bursts[j+1][0] - g[0] if j + 1 < len(bursts) else 0
        if per > 850e-6 or j + 1 == len(bursts):
            syms.append(cur); cur = ''
    return syms

def main():
    path = sys.argv[1]; ch = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    ev, fs = edges_from_sal(path, ch)
    lows = [t for t, l in ev if l == 0]
    for frame in split(lows, 50e-3):
        if len(frame) < 50:
            print(f'{frame[0]:9.4f} s  Einzelimpuls'); continue
        print(f'{frame[0]:9.4f} s  Telegramm, {1e3*(frame[-1]-frame[0]):.1f} ms')
        for k, part in enumerate(split(frame, 5e-3)):
            # Teil 2 wird wegen des 124-us-Rasters mit groesserem Fenster gebuendelt
            bursts = split(part, 100e-6 if k == 0 else 140e-6)
            if k:
                bursts = bursts[1:]         # Praeambel (reiner 8-kHz-Abschnitt) ueberspringen
            groups = decode_part(bursts, k)
            out = []
            for g in groups:
                bits = g.replace('S', '0').replace('L', '1')
                if len(bits) == 9:
                    par = 'ungerade' if bits.count('1') % 2 else 'gerade'
                    out.append(f'{bits[:8]}|{bits[8]} (0x{int(bits[:8],2):02X}, {par})')
                else:
                    out.append(bits)
            print(f'   Teil {k+1}: ' + '  '.join(out))

if __name__ == '__main__':
    main()
