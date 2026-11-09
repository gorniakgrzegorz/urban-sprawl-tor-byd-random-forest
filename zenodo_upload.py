"""Wgrywa pliki (np. rastry GeoTIFF) do rekordu Zenodo przez REST API i ustawia metadane.

Użycie (lokalnie lub w GitHub Actions):
    ZENODO_TOKEN=... python zenodo_upload.py --metadata zenodo_dataset.json --files pliki/*.tif pliki/README_rastry.md
    ZENODO_TOKEN=... python zenodo_upload.py --metadata zenodo_dataset.json --files ... --new-version 1234567 --publish

Argumenty:
    --metadata   plik JSON z polem "metadata" w formacie Zenodo (title, upload_type, description, creators, license, keywords, version, related_identifiers)
    --files      lista plików do wgrania
    --new-version ID istniejącego rekordu (tworzy nową wersję zamiast nowego rekordu)
    --publish    publikuje rekord po wgraniu (bez tej flagi zostaje szkic do przejrzenia w przeglądarce)
    --sandbox    używa sandbox.zenodo.org (osobny token!)

Token: konto Zenodo -> Applications -> Personal access tokens -> zakresy deposit:write i deposit:actions.
"""
import argparse, json, os, sys, time, urllib.request, urllib.error


def api(base, token, method, path, data=None, raw=None, ctype='application/json'):
    url = path if path.startswith('http') else base + path
    sep = '&' if '?' in url else '?'
    req = urllib.request.Request(url + sep + 'access_token=' + token, method=method)
    body = None
    if data is not None:
        body = json.dumps(data).encode(); req.add_header('Content-Type', ctype)
    elif raw is not None:
        body = raw; req.add_header('Content-Type', 'application/octet-stream')
    try:
        with urllib.request.urlopen(req, body, timeout=600) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        sys.exit('Zenodo %s %s -> HTTP %s: %s' % (method, path, e.code, e.read().decode()[:500]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--metadata', required=True)
    ap.add_argument('--files', nargs='+', required=True)
    ap.add_argument('--new-version', default=None)
    ap.add_argument('--publish', action='store_true')
    ap.add_argument('--sandbox', action='store_true')
    a = ap.parse_args()
    token = os.environ.get('ZENODO_TOKEN')
    if not token: sys.exit('brak ZENODO_TOKEN w środowisku')
    base = 'https://sandbox.zenodo.org/api' if a.sandbox else 'https://zenodo.org/api'
    meta = json.load(open(a.metadata, encoding='utf-8'))
    if 'metadata' not in meta: meta = {'metadata': meta}

    if a.new_version:
        dep = api(base, token, 'POST', '/deposit/depositions/%s/actions/newversion' % a.new_version)
        dep = api(base, token, 'GET', dep['links']['latest_draft'])
        for f in dep.get('files', []):  # nowa wersja dziedziczy pliki; usuwamy, żeby wgrać aktualne
            api(base, token, 'DELETE', '/deposit/depositions/%s/files/%s' % (dep['id'], f['id']))
    else:
        dep = api(base, token, 'POST', '/deposit/depositions', data={})
    dep_id = dep['id']; bucket = dep['links']['bucket']
    print('rekord (szkic):', dep_id, dep['links'].get('html'))

    for path in a.files:
        name = os.path.basename(path)
        size = os.path.getsize(path)
        print('wgrywanie %s (%.1f MB)' % (name, size / 1e6), flush=True)
        with open(path, 'rb') as fh:
            t0 = time.time()
            api(base, token, 'PUT', bucket + '/' + urllib.request.quote(name), raw=fh.read())
        print('  ok, %.0f s' % (time.time() - t0))

    dep = api(base, token, 'PUT', '/deposit/depositions/%s' % dep_id, data=meta)
    print('metadane ustawione; DOI zarezerwowany:', dep.get('metadata', {}).get('prereserve_doi', {}).get('doi'))
    if a.publish:
        dep = api(base, token, 'POST', '/deposit/depositions/%s/actions/publish' % dep_id)
        print('opublikowano:', dep.get('doi'), dep['links'].get('record_html'))
        print('concept DOI:', dep.get('conceptdoi'))
    else:
        print('szkic gotowy do przejrzenia i publikacji w przeglądarce:', dep['links'].get('html'))


if __name__ == '__main__':
    main()
