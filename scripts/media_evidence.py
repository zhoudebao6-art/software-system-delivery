"""Generate complete technical video evidence; independent ultra grants visual acceptance."""
import argparse
import json
import os
from pathlib import Path
from common import digest,no_links,read_json,state,delivery_paths
from _video_evidence_core import generate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',required=True);p.add_argument('--recording',required=True);p.add_argument('--output',required=True)
    p.add_argument('--ffmpeg',default=os.environ.get('SSD_FFMPEG'));p.add_argument('--ffprobe',default=os.environ.get('SSD_FFPROBE'))
    a=p.parse_args()
    try:
        workspace,output,run=state(a.workspace)
        dest=no_links(a.output);record_path=no_links(a.recording)
        if workspace not in dest.parents or workspace not in record_path.parents:raise ValueError('Evidence/recording must stay in internal workspace')
        record=read_json(record_path);video=delivery_paths(run,output)['video']
        if record.get('video_sha256')!=digest(video) or record.get('continuous_capture') is not True:raise ValueError('Actual unchanged continuous capture receipt required')
        report=generate(video,dest,5,60,None,{'ffmpeg':a.ffmpeg,'ffprobe':a.ffprobe},record['events'])
        print(json.dumps({'status':'technical_evidence_ready','timeline':str(dest/'timeline.json'),
                          'duration':report['duration'],'visual_acceptance':False},ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError,RuntimeError) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
