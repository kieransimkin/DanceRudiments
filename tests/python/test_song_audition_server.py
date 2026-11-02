"""Private audition transport: synthetic data, no masters or mocap fixtures."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar

TOOLS=Path(__file__).resolve().parents[2]/'tools'
sys.path.insert(0,str(TOOLS))
import serve_song_loop_preview as server
from build_song_loop_preview import collection_jobs


class AuditionTransportTests(unittest.TestCase):
    def test_capability_host_origin_and_explicit_allowlist(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'index.html').write_text('synthetic audition')
            (root/'private.txt').write_text('must never be served')
            (root/'report.json').write_text(json.dumps(dict(format='dancerudiments.song-motion-loop-preview',motions=[],songs=[])))
            app,url=server.create_server(root)
            worker=threading.Thread(target=app.serve_forever,daemon=True);worker.start()
            client=build_opener(HTTPCookieProcessor(CookieJar()))
            base=url.split('?')[0]
            try:
                with self.assertRaises(HTTPError) as failure:client.open(base)
                self.assertEqual(failure.exception.code,403)
                self.assertEqual(client.open(url).read(),b'synthetic audition')
                for path in ('private.txt','../private.txt','%2e%2e/private.txt'):
                    with self.assertRaises(HTTPError) as failure:client.open(base+path)
                    self.assertEqual(failure.exception.code,404)
                for headers in ({'Origin':'https://foreign.invalid'},{'Host':'foreign.invalid'}):
                    with self.assertRaises(HTTPError) as failure:client.open(Request(base,headers=headers))
                    self.assertEqual(failure.exception.code,403)
                self.assertIn('no-store',client.open(base).headers['Cache-Control'])
            finally:app.shutdown();app.server_close();worker.join(timeout=2)
            self.assertFalse(worker.is_alive())

    def test_collection_rejects_traversal_duplicate_and_changed_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);job=root/'action';job.mkdir()
            (job/'job.json').write_text(json.dumps(dict(source_original_sha256='a'*64,profile_sha256='b'*64)))
            action=dict(relative_output='action',source_sha256='a'*64,profile_sha256='b'*64)
            index=dict(format='dancerudiments.source-motion-collection-analysis',schema_version=1,truncated=False,actions=[action])
            path=root/'index.json'
            def save():path.write_text(json.dumps(index))
            save();self.assertEqual(collection_jobs(path)[0],[job])
            action['relative_output']='../escape';save()
            with self.assertRaisesRegex(ValueError,'escapes'):collection_jobs(path)
            action['relative_output']='action';action['profile_sha256']='c'*64;save()
            with self.assertRaisesRegex(ValueError,'identity'):collection_jobs(path)
            action['profile_sha256']='b'*64;index['actions']=[action,action];save()
            with self.assertRaisesRegex(ValueError,'Duplicate'):collection_jobs(path)
            index['actions']=[action];index['truncated']=True;save()
            with self.assertRaisesRegex(ValueError,'complete'):collection_jobs(path)


if __name__=='__main__':unittest.main()
