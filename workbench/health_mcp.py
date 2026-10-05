"""Stateless read-only MCP tools over the same private health database."""
import datetime as dt
import json
import wellbeing
from health_metrics import METRICS

TOOLS = [
    {'name':'get_health_overview','description':'读取今天的活动、最近一晚睡眠、近期训练和真实同步状态；缺失不代表零。',
     'inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
    {'name':'get_health_history','description':'按日期读取已保存的睡眠或健康指标，不做诊断。',
     'inputSchema':{'type':'object','properties':{'metric':{'type':'string','enum':['sleep_analysis',*METRICS]},
         'start':{'type':'string','description':'YYYY-MM-DD'},'end':{'type':'string','description':'YYYY-MM-DD'}},
         'required':['metric'],'additionalProperties':False}},
    {'name':'get_workouts','description':'读取日期范围内已收到的训练记录，包含时长、来源和可用的热量/距离。',
     'inputSchema':{'type':'object','properties':{'start':{'type':'string'},'end':{'type':'string'}},'additionalProperties':False}},
]
for tool in TOOLS:
    tool['annotations']={'readOnlyHint':True,'destructiveHint':False,'idempotentHint':True,'openWorldHint':False}


def dates(args):
    end=dt.date.fromisoformat(args.get('end',wellbeing.today()))
    start=dt.date.fromisoformat(args.get('start',(end-dt.timedelta(days=6)).isoformat()))
    if not 0 <= (end-start).days <= 90:
        raise ValueError('日期范围需要在 0 到 90 天之间')
    return start.isoformat(),end.isoformat()


def call(name,args):
    if not isinstance(args,dict):
        raise ValueError('参数需要是对象')
    if name=='get_health_overview':
        data=wellbeing.health_snapshot()
        return {**data,'sleep':data['sleep'][:2],'metrics':[m for m in data['metrics'] if m['day']==data['today']], 'workouts':data['workouts'][:5]}
    start,end=dates(args)
    with wellbeing.connect() as db:
        if name=='get_workouts':
            rows=db.execute('SELECT summary,received FROM workouts WHERE day BETWEEN ? AND ? ORDER BY day DESC',(start,end))
        elif name=='get_health_history':
            metric=args.get('metric')
            if metric=='sleep_analysis':
                rows=db.execute('SELECT summary,received FROM sleep_days WHERE day BETWEEN ? AND ? ORDER BY day',(start,end))
            elif metric in METRICS:
                rows=db.execute('SELECT summary,received FROM health_metrics WHERE name=? AND day BETWEEN ? AND ? ORDER BY day',(metric,start,end))
            else:raise ValueError('指标不支持')
        else:raise ValueError('工具不存在')
        return {'start':start,'end':end,'records':[{**json.loads(r[0]),'received':r[1]} for r in rows]}


def handle(request):
    if not isinstance(request,dict) or request.get('jsonrpc')!='2.0' or not isinstance(request.get('method'),str):
        return {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid Request'}}
    if 'id' not in request:
        return None
    identity=request['id'];method=request['method'];params=request.get('params',{})
    if not isinstance(params,dict):
        return {'jsonrpc':'2.0','id':identity,'error':{'code':-32602,'message':'Invalid params'}}
    if method=='initialize':
        version=params.get('protocolVersion')
        result={'protocolVersion':version if version in ('2025-06-18','2025-03-26','2024-11-05') else '2025-06-18',
            'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'zelong-health','version':'1.0.0'}}
    elif method=='ping':result={}
    elif method=='tools/list':result={'tools':TOOLS}
    elif method=='tools/call':
        try:
            value=call(params.get('name'),params.get('arguments',{}))
            result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}
        except (ValueError,TypeError,KeyError):
            result={'content':[{'type':'text','text':'工具或参数无效，请检查名称、指标和日期范围。'}],'isError':True}
    else:return {'jsonrpc':'2.0','id':identity,'error':{'code':-32601,'message':'Method not found'}}
    return {'jsonrpc':'2.0','id':identity,'result':result}
