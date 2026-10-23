"""Register and close only verified, dedicated Windows case processes."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from common import no_links, read_json, write_json

def inventory():
    if os.name!='nt': raise ValueError('Process ownership guard requires Windows')
    script=r'''$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$ports=@(Get-CimInstance -Namespace root/StandardCimv2 -ClassName MSFT_NetTCPConnection -Filter 'State = 2')
$rows=@(Get-CimInstance Win32_Process | ForEach-Object {
  $p=$_
  [pscustomobject]@{pid=[int]$p.ProcessId;parent_pid=[int]$p.ParentProcessId;name=[string]$p.Name;command=[string]$p.CommandLine;created_ticks=if($p.CreationDate){$p.CreationDate.ToUniversalTime().ToFileTimeUtc()}else{0};ports=@($ports | Where-Object {$_.OwningProcess -eq $p.ProcessId} | Select-Object -ExpandProperty LocalPort -Unique)}
})
ConvertTo-Json -Depth 4 -Compress -InputObject $rows
'''
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
        capture_output=True,text=True,encoding='utf-8',timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode: raise ValueError('OS identity query failed: '+p.stderr[-800:])
    rows=json.loads(p.stdout.lstrip('\ufeff'))
    for r in rows:
        r['command_sha256']=hashlib.sha256(r['command'].encode('utf-8')).hexdigest()
    return rows

def command_owned(workspace,command):
    path=str(Path(workspace).resolve()).replace('\\','/').rstrip('/').casefold()
    value=command.replace('\\','/').casefold()
    return bool(re.search(r'(?:^|[\s\"\'=])'+re.escape(path)+r'(?:/|[\s\"\']|$)',value))

def ancestor_ids(rows):
    lookup={r['pid']:r for r in rows}; result=set(); current=os.getpid()
    while current and current not in result:
        result.add(current);current=lookup.get(current,{}).get('parent_pid',0)
    return result

def protected(row,ancestors):
    name=row['name'].casefold(); command=row['command'].casefold()
    return (row['pid'] in ancestors or name in {'codex.exe','chatgpt.exe','chrome.exe','msedge.exe'} or
            any(x in command for x in ('launch_codex_app_tools_mcp','mcp-server','mcp_server','patenttitlebot','hermes')))

def same(left,right):
    return bool(left and right and all(left[k]==right[k] for k in ('pid','created_ticks','command_sha256')))

def owned_processes(workspace,rows):
    ancestors=ancestor_ids(rows)
    return [r for r in rows if background_entry_owned(workspace,r) and not protected(r,ancestors)]

def python_script_argument(args):
    """Conservatively identify Python's executed file, never a code/module argv."""
    args=list(args)
    while args:
        value=args.pop(0)
        if value=='--':return args[0] if args else None
        if not value.startswith('-'):return value
        if value=='-' or value.startswith('--'):return None
        # CPython permits attached option values and short option clusters.
        # W/X consume the rest of this token (or the following token), whereas
        # c/m select an entirely different entry mode, including -IcCODE.
        flags=value[1:]
        for index,flag in enumerate(flags):
            if flag in 'cm':return None
            if flag in 'WX':
                if index+1==len(flags):
                    if not args:return None
                    args.pop(0)
                break
            if flag not in 'bBdEiIOPqRsSuvx':return None
    return None

def background_entry_owned(workspace,row):
    """A path in a read/search command is not a service ownership proof."""
    if not command_owned(workspace,row.get('command','')):return False
    name=row.get('name','').casefold()
    # Parse the actual executable's script position. A later argv path is never
    # an invoked entry, even when it happens to end in .py/.js.
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    shell.CommandLineToArgvW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype=ctypes.POINTER(wintypes.LPWSTR)
    count=ctypes.c_int();pointer=shell.CommandLineToArgvW(row['command'],ctypes.byref(count))
    if not pointer:return False
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    try:args=[pointer[i] for i in range(count.value)][1:]
    finally:kernel.LocalFree(pointer)
    entry=None;suffixes=set()
    if name in {'python.exe','pythonw.exe'}:
        suffixes={'.py'}
        entry=python_script_argument(args)
    elif name in {'node.exe','bun.exe','deno.exe'}:
        suffixes={'.js','.mjs','.cjs','.ts'}
        if args and args[0] in {'run'}:args.pop(0)
        # Ambiguous option forms require a dedicated supervisor instead.
        if args and not args[0].startswith('-'):entry=args[0]
    elif name in {'powershell.exe','pwsh.exe'}:
        suffixes={'.ps1'}
        lower=[a.casefold() for a in args]
        if '-command' in lower or '-encodedcommand' in lower:return False
        if '-file' in lower:
            i=lower.index('-file')
            if i+1<len(args):entry=args[i+1]
    if not entry:return False
    try:
        target=no_links(entry);root=no_links(workspace)
        return root in target.parents and target.is_file() and target.suffix.casefold() in suffixes
    except (ValueError,OSError):return False

def descendants(rows,roots):
    """Only a live, older, exact parent identity proves a descendant edge."""
    known={r['pid']:r for r in roots};found=[]
    for _ in range(len(rows)+1):
        changed=False
        for row in rows:
            parent=known.get(row['parent_pid'])
            if row['pid'] in known or not parent or row['created_ticks']<parent['created_ticks']:continue
            item=dict(row);item['ownership_root']={k:parent[k] for k in ('pid','created_ticks','command_sha256')}
            known[item['pid']]=item;found.append(item);changed=True
        if not changed:break
    return found

def register(workspace,pid):
    workspace=no_links(workspace)
    record=workspace/'.ssd/processes.json'
    if not (workspace/'.ssd/run.json').is_file(): raise ValueError('Prepare the case first')
    rows=inventory();lookup={r['pid']:r for r in rows};current=lookup.get(pid)
    ancestors=ancestor_ids(rows)
    if not current or protected(current,ancestors) or not current['command'] or not current['created_ticks']:
        raise ValueError('Missing or protected process; registration refused')
    value=read_json(record) if record.exists() else {'workspace':str(workspace),'processes':[]}
    if value['workspace']!=str(workspace): raise ValueError('Registry workspace mismatch')
    direct=background_entry_owned(workspace,current)
    root=None
    if not direct:
        parent=current['parent_pid']; visited=set();previous=current
        while parent and parent not in visited:
            visited.add(parent);row=lookup.get(parent)
            if not row or row['created_ticks']>previous['created_ticks']: break
            if any(same(saved,row) for saved in value['processes']) and (background_entry_owned(workspace,row) or any(same(saved,row) and saved.get('ownership_root') for saved in value['processes'])):
                root={k:row[k] for k in ('pid','created_ticks','command_sha256')};break
            previous=row;parent=row['parent_pid']
        if root is None: raise ValueError('No bounded case path or live registered case ancestor')
    current['ownership_root']=root
    if not any(same(saved,current) for saved in value['processes']):
        value['processes'].append(current)
    for row in descendants(rows,[current]):
        if protected(row,ancestors):continue
        if not any(same(saved,row) for saved in value['processes']):value['processes'].append(row)
    write_json(record,value)
    return {'registered':pid,'name':current['name'],'ports':current['ports']}

def retain_exact(expected):
    """An open handle prevents identity/PID recycling during tree cleanup."""
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    kernel.GetProcessTimes.restype=wintypes.BOOL
    kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT];kernel.TerminateProcess.restype=wintypes.BOOL
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x100000|0x1000|1,False,expected['pid'])
    if not handle: raise ValueError('Could not retain exact process handle')
    try:
        times=[wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*[ctypes.byref(x) for x in times]): raise ValueError('Creation time query failed')
        ticks=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
        if ticks//10 != expected['created_ticks']//10: raise ValueError('PID was reused')
        rows=inventory();current=next((r for r in rows if r['pid']==expected['pid']),None)
        if not same(expected,current) or protected(current,ancestor_ids(rows)):
            raise ValueError('Process identity changed or is protected')
        if not set(current['ports']).issubset(set(expected['ports'])):
            raise ValueError('Process acquired unregistered ports; recheck exclusive ownership')
        return kernel,handle
    except BaseException:
        kernel.CloseHandle(handle);raise

def terminate_exact(expected):
    kernel,handle=retain_exact(expected)
    try:
        if not kernel.TerminateProcess(handle,0) and kernel.WaitForSingleObject(handle,5000)!=0:
            raise ValueError('Exact process termination failed')
        if kernel.WaitForSingleObject(handle,5000)!=0:raise ValueError('Process did not exit')
    finally:kernel.CloseHandle(handle)

def stop(workspace):
    workspace=no_links(workspace)
    if not (workspace/'.ssd/run.json').is_file(): raise ValueError('Prepare the case first')
    path=workspace/'.ssd/processes.json'
    record=read_json(path) if path.exists() else {'workspace':str(workspace),'processes':[]}
    if record['workspace']!=str(workspace): raise ValueError('Registry workspace mismatch')
    rows=inventory();lookup={r['pid']:r for r in rows};results=[]
    registered=list(record['processes']);held={};stopped=set()
    try:
        # Retain all verified roots before ending any process. Refresh while
        # those handles are held, then stop parents first to prevent new births.
        for saved in list(registered):
            current=lookup.get(saved['pid'])
            if not same(saved,current):
                results.append({'pid':saved['pid'],'status':'original_exited','replacement_preserved':bool(current)});continue
            try:
                if not saved.get('ownership_root') and not background_entry_owned(workspace,current):raise ValueError('Invoked case entry ownership missing')
                held[saved['pid']]=(saved,*retain_exact(saved))
            except (ValueError,OSError) as e:results.append({'pid':saved['pid'],'status':'pending','reason':str(e)})
        for _ in range(16):
            live=inventory()
            # Known parent PIDs cannot be reused while their handles are held,
            # including parents that have just exited. This also captures late
            # children and grandchildren after their parent has terminated.
            added=descendants(live,[value[0] for value in held.values()])
            for saved in added:
                if saved['pid'] in held:continue
                registered.append(saved)
                try:
                    if protected(saved,ancestor_ids(live)):raise ValueError('Protected descendant preserved')
                    held[saved['pid']]=(saved,*retain_exact(saved))
                except (ValueError,OSError) as e:results.append({'pid':saved['pid'],'status':'pending','reason':str(e)})
            pending=[value for pid,value in held.items() if pid not in stopped]
            if not pending and not added:break
            for saved,kernel,handle in pending:
                try:
                    if kernel.WaitForSingleObject(handle,0)!=0:
                        # A retained child can finish between the first wait
                        # and termination (for example when its launcher exits).
                        # Only the same kernel handle's signaled state proves exit.
                        if not kernel.TerminateProcess(handle,0) and kernel.WaitForSingleObject(handle,5000)!=0:
                            raise ValueError('Exact process termination failed')
                        if kernel.WaitForSingleObject(handle,5000)!=0:raise ValueError('Process did not exit')
                    stopped.add(saved['pid']);results.append({'pid':saved['pid'],'status':'stopped'})
                except (ValueError,OSError) as e:
                    stopped.add(saved['pid']);results.append({'pid':saved['pid'],'status':'pending','reason':str(e)})
        else:results.append({'status':'pending','reason':'Descendant tree did not quiesce'})
        after=inventory()
    finally:
        for saved,kernel,handle in held.values():kernel.CloseHandle(handle)
    remaining=owned_processes(workspace,after)
    for row in after:
        if any(same(row,saved) for saved in registered) and not any(same(row,r) for r in remaining): remaining.append(row)
    for row in descendants(after,registered):
        if not any(same(row,r) for r in remaining):remaining.append(row)
    ports=sorted({port for saved in registered for port in saved['ports']})
    occupied=[{'port':port,'pid':row['pid']} for row in after for port in row['ports'] if port in ports]
    receipt={'status':'stopped' if not remaining and not occupied and not any(r['status']=='pending' for r in results) else 'cleanup_pending',
             'workspace':str(workspace),'processes':results,'remaining':remaining,'ports_still_listening':occupied}
    write_json(workspace/'.ssd/cleanup.json',receipt)
    return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['register','inspect','stop']);p.add_argument('--workspace',required=True);p.add_argument('--pid',type=int)
    a=p.parse_args()
    try:
        if a.action=='register':
            if not a.pid: raise ValueError('--pid required')
            value=register(a.workspace,a.pid)
        elif a.action=='inspect': value={'owned':owned_processes(a.workspace,inventory())}
        else: value=stop(a.workspace)
        print(json.dumps(value,ensure_ascii=False,indent=2))
        return 2 if value.get('status')=='cleanup_pending' else 0
    except (ValueError,OSError,subprocess.SubprocessError) as e:
        print('ERROR: '+str(e),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
