#!/usr/bin/env python3
"""Build a Chinese-localized APK from the reference restoration APK.

Keeps every existing byte (including the crash/network fixes in
libcocos2dcpp.so) and only swaps the text tables:

  assets/textdata_en.dat  -> Chinese   (the launcher's fallback language file)
  assets/textdata_ko.dat  -> Chinese
  assets/textdata_zh.dat  -> Chinese   (added, used when the device locale is zh)

Usage:
  python3 zh/build_zh_apk.py <patched.so> <chinese.dat> <out.apk>
"""
import zipfile, os, sys, subprocess, glob

ROOT = os.environ.get('DS_ROOT', os.getcwd())
SRC = os.environ.get('BASE_APK', 'base/darkness_survival_restored.apk')  # your own copy of the base APK
SO_ENTRY = 'lib/armeabi/libcocos2dcpp.so'
TEXT_ENTRIES = ['assets/textdata_en.dat', 'assets/textdata_ko.dat']
NEW_ENTRY = 'assets/textdata_zh.dat'
DROP = {'META-INF/MANIFEST.MF'}
DROP_EXT = ('.SF', '.RSA', '.DSA', '.EC')


def build(patched_so, chinese_dat, out_unsigned, overlay_dir=None, verbose=True, new_entry='assets/textdata_zh.dat'):
    os.makedirs(os.path.dirname(out_unsigned), exist_ok=True)
    if os.path.exists(out_unsigned):
        os.remove(out_unsigned)
    text = open(chinese_dat, 'rb').read()
    so = open(patched_so, 'rb').read()
    overlay = {}
    dirs = overlay_dir if isinstance(overlay_dir, (list, tuple)) else [overlay_dir]
    for d in dirs:
        if not d:
            continue
        for p in glob.glob(f'{d}/**/*', recursive=True):
            if os.path.isfile(p):
                overlay['assets/' + os.path.relpath(p, d).replace(os.sep, '/')] = p
    global NEW_ENTRY
    NEW_ENTRY = new_entry
    zin = zipfile.ZipFile(SRC)
    zout = zipfile.ZipFile(out_unsigned, 'w', zipfile.ZIP_DEFLATED)
    n = 0
    seen_new = False
    overlaid = 0
    for info in zin.infolist():
        name = info.filename
        base = name.rsplit('/', 1)[-1]
        if name in DROP or (name.startswith('META-INF/') and base.upper().endswith(DROP_EXT)):
            if verbose:
                print('  drop old signature:', name)
            continue
        if name == SO_ENTRY:
            data = so
        elif name in TEXT_ENTRIES:
            data = text
        elif name == NEW_ENTRY:
            data = text
        elif name in overlay:
            data = open(overlay.pop(name), 'rb').read()
            overlaid += 1
        else:
            data = zin.read(name)
        zi = zipfile.ZipInfo(name, date_time=info.date_time)
        zi.compress_type = info.compress_type
        zi.external_attr = info.external_attr
        zi.internal_attr = info.internal_attr
        zi.create_system = info.create_system
        zout.writestr(zi, data)
        n += 1
        if name == NEW_ENTRY:
            seen_new = True
    for name, p in sorted(overlay.items()):
        zi = zipfile.ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        zout.writestr(zi, open(p, 'rb').read())
        n += 1
        print('  added', name)
    if not seen_new:
        zi = zipfile.ZipInfo(NEW_ENTRY, date_time=(2024, 1, 1, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        zout.writestr(zi, text)
        n += 1
        print('  added', NEW_ENTRY)
    zout.close(); zin.close()
    if verbose:
        print(f'  wrote {n} entries ({overlaid} localized assets) -> {out_unsigned} '
              f'({os.path.getsize(out_unsigned):,} bytes)')
    return out_unsigned


JDK = os.environ.get('JAVA_HOME', '/usr/lib/jvm/java-21-openjdk')


def sign(unsigned, out_signed, keystore=f'{ROOT}/sign/ds.keystore', alias='ds', pw='darkness'):
    exports = []
    for pkg in ('sun.security.x509', 'sun.security.pkcs', 'sun.security.util',
                'sun.security.timestamp', 'sun.security.provider.certpath'):
        exports += [f'--add-exports=java.base/{pkg}=ALL-UNNAMED',
                    f'--add-opens=java.base/{pkg}=ALL-UNNAMED']
    cp = f'{ROOT}/libs/apksig-8.13.2.jar:{ROOT}/sign'
    r = subprocess.run([f'{JDK}/bin/java'] + exports + ['-cp', cp, 'Sign', keystore, pw, alias,
                                                        unsigned, out_signed],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    if r.returncode != 0:
        print(r.stderr); raise SystemExit('signing failed')
    return out_signed


if __name__ == '__main__':
    so, dat, out = sys.argv[1], sys.argv[2], sys.argv[3]
    dirs = [f'{ROOT}/work/assets_zh']
    if os.path.isdir(f'{ROOT}/work/assets_font') and os.environ.get('NO_FONT_SWAP') != '1':
        dirs.append(f'{ROOT}/work/assets_font')
    entry = sys.argv[4] if len(sys.argv) > 4 else 'assets/textdata_zh.dat'
    u = build(so, dat, f'{ROOT}/work/unsigned_zh.apk', overlay_dir=dirs, new_entry=entry)
    sign(u, out)
    print('final:', out, f'{os.path.getsize(out):,} bytes')
