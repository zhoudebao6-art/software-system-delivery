"""Independent software-only delivery paths and immutable receipts."""
import hashlib
import json
from pathlib import Path
import stat


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def no_links(path):
    value = Path(path).absolute()
    for item in (value, *value.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Link/reparse point not accepted in artifact paths: '+str(item))
    return value.resolve()


def inside(root, relative, must_exist=True):
    root = no_links(root)
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Expected relative child path')
    target = no_links(root / rel)
    if root not in target.parents:
        raise ValueError('Path escapes root')
    if must_exist and not target.exists():
        raise ValueError('Missing file: '+str(target))
    return target


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value, exclusive=False):
    target = no_links(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x' if exclusive else 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def state(workspace):
    workspace = no_links(workspace)
    run = read_json(inside(workspace, '.ssd/run.json'))
    if run.get('profile') != 'software-only-v1' or run.get('workspace') != str(workspace):
        raise ValueError('Invalid isolated software-only run')
    return workspace, no_links(run['output']), run


def delivery_paths(run, output=None):
    root = no_links(output or run['output'])
    return {'output': root, 'system': root/'系统材料',
            'source_zip': root/'系统材料'/'源代码.zip',
            'video': root/'系统材料'/'操作视频.mp4',
            'data_dir': root/'系统材料'/'数据'}
