"""Hash existing evidence files. Does not invent checks, facts, approvals or missing files."""
import argparse
import json
from common import inside,state,read_json,write_json
from ssdflow import make_ref


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',required=True);p.add_argument('--map',required=True);p.add_argument('--output',required=True)
    a=p.parse_args()
    try:
        workspace,_,run=state(a.workspace)
        mappings=read_json(inside(workspace,a.map));result={}
        if not isinstance(mappings,dict) or not mappings:raise ValueError('Explicit nonempty key-to-existing-relative-file map required')
        for key,relative in mappings.items():
            result[key]=make_ref(workspace,inside(workspace,relative))
        output=inside(workspace,a.output,must_exist=False)
        write_json(output,result,exclusive=True)
        print(json.dumps({'run_id':run['run_id'],'evidence_manifest':make_ref(workspace,output),'keys':list(result)},ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
