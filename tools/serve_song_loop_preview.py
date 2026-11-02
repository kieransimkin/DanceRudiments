#!/usr/bin/env python3
"""Serve a private, read-only song audition on loopback with an asset allowlist.

The printed capability URL is a local handoff, not a public publication URL.
No uploads, directory listing, file selection API or authoring writes exist.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path, PurePosixPath
import secrets
from urllib.parse import parse_qs, unquote, urlsplit


def safe_asset(root, name):
    relative=PurePosixPath(name)
    if (not name or relative.is_absolute() or '\\' in name or ':' in name
            or any(part in ('.','..') for part in name.split('/'))):
        raise ValueError('Unsafe audition asset path')
    unresolved=root.joinpath(*relative.parts)
    path=unresolved.resolve()
    if (not path.is_relative_to(root) or not path.is_file()
            or any(p.is_symlink() for p in (unresolved,*unresolved.parents))):
        raise ValueError('Audition assets must be regular files within the site')
    return path


def inventory(directory):
    root=Path(directory).resolve()
    report=json.loads(safe_asset(root,'report.json').read_text(encoding='utf-8'))
    if report.get('format')!='dancerudiments.song-motion-loop-preview':
        raise ValueError('Expected a generated song audition')
    paths={'index.html','report.json'}
    for motion in report['motions']:
        for field in ('preview_asset','native_asset'):
            if motion.get(field):paths.add(motion[field]['path'])
    for song in report['songs']:
        if song.get('local_audio'):paths.add(song['local_audio']['path'])
    if report.get('mesh_audition'):
        receipt=safe_asset(root,'mesh/build.json')
        if hashlib.sha256(receipt.read_bytes()).hexdigest()!=report['mesh_audition']['build_sha256']:
            raise ValueError('Mesh build receipt changed')
        mesh=json.loads(receipt.read_text(encoding='utf-8'))
        if mesh.get('scope')!='local-read-only-audition':raise ValueError('Invalid mesh site scope')
        paths.add('mesh/build.json')
        paths.update('mesh/'+name for name in mesh['files'])
    return root,{name:safe_asset(root,name) for name in paths}


def create_server(directory,port=0):
    root,assets=inventory(directory)
    capability=secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # Do not log capability-bearing URLs.

        def do_HEAD(self):self.respond(head=True)
        def do_GET(self):self.respond()

        def respond(self,head=False):
            expected=f'127.0.0.1:{self.server.server_port}'
            origin='http://'+expected
            if self.headers.get('Host')!=expected or self.headers.get('Origin',origin)!=origin:
                self.send_error(403);return
            cookie_name=f'dr_audition_{self.server.server_port}'
            query=urlsplit(self.path)
            supplied=parse_qs(query.query).get('token',[''])[0]
            if query.path=='/' and supplied and hmac.compare_digest(supplied,capability):
                self.send_response(303)
                self.send_header('Location','/')
                self.send_header('Cache-Control','no-store')
                self.send_header('Referrer-Policy','no-referrer')
                self.send_header('Set-Cookie',f'{cookie_name}={capability}; HttpOnly; SameSite=Strict; Path=/')
                self.end_headers();return
            cookie=SimpleCookie()
            try:cookie.load(self.headers.get('Cookie',''))
            except Exception:self.send_error(403);return
            supplied=cookie.get(cookie_name)
            if not supplied or not hmac.compare_digest(supplied.value,capability):
                self.send_error(403);return
            name=unquote(query.path).lstrip('/') or 'index.html'
            path=assets.get(name)
            if path is None:self.send_error(404);return
            try:
                if safe_asset(root,name)!=path:raise ValueError('Asset changed')
                content=path.read_bytes()
            except (OSError,ValueError):self.send_error(404);return
            self.send_response(200)
            self.send_header('Content-Type',mimetypes.guess_type(name)[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','SAMEORIGIN')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
            self.end_headers()
            if not head:
                try:self.wfile.write(content)
                except (ConnectionError,OSError):pass

    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    return server,f'http://127.0.0.1:{server.server_port}/?token={capability}'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--receipt',type=Path)
    args=parser.parse_args()
    server,url=create_server(args.directory,args.port)
    receipt={'url':url,'directory':str(args.directory.resolve()),'scope':'private-loopback-read-only'}
    if args.receipt:args.receipt.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
