#!/usr/bin/env python3
"""Attach original source previews and a sealed Kandi site to saved song analysis.

This command reuses the completed report; it does not rerun song inference or
change the ranking, approval status or source captures.
"""
import argparse
import json
from pathlib import Path
from build_song_loop_preview import attach_original_previews, attach_mesh_site, render_report, rerank_activity


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--collection-index',type=Path)
    parser.add_argument('--mesh-site',type=Path)
    parser.add_argument('--prefer-movement',action='store_true',help='Measure exact native clips and favour active phrases; no audio inference')
    args=parser.parse_args()
    if args.collection_index:attach_original_previews(args.directory,args.collection_index)
    if args.mesh_site:attach_mesh_site(args.directory,args.mesh_site)
    if args.prefer_movement:rerank_activity(args.directory)
    data=json.loads((args.directory/'report.json').read_text(encoding='utf-8'))
    render_report(data,args.directory)
    print(json.dumps({'motions':len(data['motions']),'mesh':bool(data.get('mesh_audition'))}))


if __name__=='__main__':main()
