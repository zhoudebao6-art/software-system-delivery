"""Astra/low only after exact real human authorization for this current run/scope."""
import hashlib
import json
from pathlib import Path
import re
from common import state,read_json,no_links
from model_proof import events


def simple_command(statement,scope):
    name=re.escape(scope)
    courtesy=r'(?:请|帮我|请帮我)?\s*'
    modifiers=r'(?:(?:请|要|需要|都|全部|直接|马上)\s*)*'
    action=r'(?:加急(?:一下|处理|办理|审核|验收)?|(?:启用|使用|采用|按)\s*(?:原加急模式|(?:gpt-6-)?Astra\s*(?:低思考|低|low)))'
    return bool(scope and re.fullmatch(r'(?:'+courtesy+name+r'\s*(?:(?:这批|本批|该批|此批)(?:案件)?\s*)?'+modifiers+action+'|'+courtesy+r'加急\s*'+name+r')[。.!！]?',statement,re.I))


def exact_context(text):
    m=re.fullmatch(r'(?:当前批次|本次批次|现在处理批次)\s*[:：=]?\s*([A-Za-z0-9_-]+)\s*[。.]?',text.strip())
    return m.group(1) if m else None


def question_answer(actual,statement,scope,requests):
    tag='send_user_message_question_reply'
    m=re.fullmatch(r'\s*<'+tag+r'>\s*(.*?)\s*</'+tag+r'>\s*',actual,re.S)
    if not m or actual.count('<'+tag+'>')!=1 or actual.count('</'+tag+'>')!=1:return False
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('Duplicate question answer key')
            value[key]=item
        return value
    try:
        replies=json.loads(m.group(1),object_pairs_hook=unique);answers=[];seen=set()
        if not isinstance(replies,list) or not replies:return False
        for reply in replies:
            if not isinstance(reply,dict) or set(reply)!={'questionItemId','question','answer'} or not all(isinstance(x,str) for x in reply.values()):return False
            if any('<'+tag in x or '</'+tag in x for x in reply.values()):return False
            ident=json.loads(reply['questionItemId'])
            if not isinstance(ident,list) or len(ident)!=3 or ident[0]!='request_user_input_async' or not isinstance(ident[1],str) or type(ident[2]) is not int or ident[2]<0:return False
            key=(ident[1],ident[2])
            if key in seen:return False
            seen.add(key);req=requests.get(ident[1])
            if not req:return False
            args=json.loads(req['arguments'],object_pairs_hook=unique);q=args['questions'][ident[2]]
            if q.get('title')!=reply['question']:return False
            answers.append(reply['answer'])
        return answers.count(statement)==1 and all(a==statement or scope not in a for a in answers)
    except (ValueError,KeyError,TypeError,IndexError):return False


def validate(workspace,record):
    workspace,_,run=state(workspace)
    if record.get('run_id')!=run['run_id'] or record.get('workspace')!=str(workspace):
        raise ValueError('Expedited authorization must bind this actual run/workspace')
    logged,meta=events(record['session_log'])
    if isinstance(meta.get('source'),dict) and meta['source'].get('subagent'):
        raise ValueError('Only actual human parent messages authorize expedited review')
    from batch_control import ROOT
    control=read_json(ROOT/'control.json') if (ROOT/'control.json').is_file() else {'batches':{}}
    matches=[(bid,b,c) for bid,b in control['batches'].items() for c in b['cases'] if c['workspace']==str(workspace)]
    if len(matches)>1:raise ValueError('Ambiguous batch binding')
    scope=record.get('scope_name','');statement=record.get('statement','')
    if not isinstance(statement,str) or statement.strip()!=statement or len(statement.splitlines())!=1:
        raise ValueError('Whole single-line scoped affirmative command required')
    allowed={run['case_id'],run['title']};batch_id=None;qualified=False;ambiguous=False
    if matches:
        batch_id,batch,case=matches[0]
        allowed|={batch_id,batch_id+'/'+run['case_id']};qualified=scope in {batch_id,batch_id+'/'+run['case_id']}
        for bid,b in control['batches'].items():
            for c in b['cases']:
                if c['workspace']!=str(workspace) and scope in {c['case_id'],c.get('title','')}:
                    if bid==batch_id:allowed.discard(scope)
                    else:ambiguous=True
    if scope not in allowed:raise ValueError('Authorization scope is not this unique current case/batch')
    implicit=bool(re.fullmatch(r'(?:这批|本批|该批|此批)(?:案件)?(?:请|要|需要|都|全部|直接|马上|\s)*加急(?:一下|处理|办理|审核|验收)?[。.!！]?',statement))
    if not implicit and not simple_command(statement,scope):
        raise ValueError('Conditional/quoted/material/question/fast wording does not authorize Astra')
    requests={};last_context=None;found=False
    for event in logged:
        payload=event.get('payload',{})
        if event.get('type')!='response_item':continue
        if payload.get('type')=='function_call' and payload.get('name','').split('.')[-1]=='request_user_input_async':
            call_id=payload.get('call_id');requests[call_id]=None if call_id in requests else payload;continue
        if payload.get('type')!='message' or payload.get('role')!='user':continue
        actual='\n'.join(p.get('text','') for p in payload.get('content',[]))
        actual_hash=hashlib.sha256(actual.encode()).hexdigest()
        matched=actual.strip()==statement or (not implicit and question_answer(actual,statement,scope,requests))
        if matched and actual_hash==record.get('user_message_sha256'):
            if implicit:
                context=record.get('scope_context',{})
                if (not matches or scope!=batch_id or not last_context or last_context['batch_id']!=batch_id
                        or context.get('batch_id')!=batch_id or context.get('user_message_sha256')!=last_context['sha256']
                        or context.get('statement')!=last_context['statement']
                        or context.get('manifest_sha256')!=batch['case_manifest_sha256']
                        or str(no_links(context.get('root','')))!=str(no_links(ROOT))):
                    raise ValueError('Implicit batch command needs exact prior human context and frozen manifest binding')
            elif batch_id and not qualified and ((last_context and last_context['batch_id']!=batch_id) or (ambiguous and (not last_context or last_context['batch_id']!=batch_id))):
                raise ValueError('Reused bare name needs matching explicit human current-batch context')
            found=True
        if re.search(r'批次|当前批|这批|本批|该批|另.{0,8}批|切换.{0,8}批|下一批|\bbatch\b',actual,re.I):
            last_context={'batch_id':exact_context(actual),'statement':actual.strip(),'sha256':actual_hash}
    if not found:raise ValueError('Exact affirmative authorization not found in real parent user message')
    return {'route':'original-expedited','model':'gpt-6-astra','effort':'low','parent_session_id':meta['id'],
            'run_id':run['run_id'],'scope_name':scope,'user_message_sha256':record['user_message_sha256'],
            'batch_id':batch_id,'manifest_sha256':matches[0][1]['case_manifest_sha256'] if matches else None}
