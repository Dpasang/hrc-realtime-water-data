"""Build monthly station series and LongRiver-style daily/latest views."""
import collections,csv,datetime,hashlib,io,json,pathlib,statistics
import collector

ROOT=pathlib.Path(__file__).resolve().parent
TZ=collector.TZ
METRICS=['water_level_value','flow_value','limit_value_number']
STATION_COLUMNS=['station_key','river','station','observed_at','water_level_value','flow_value','units','unit_status',
                 'limit_value_raw','limit_value_number','limit_value_semantics','quality','raw_variants',
                 'source_occurrences','first_captured_at','last_captured_at','source_manifests','original_fields']
MONTH_COLUMNS=['month','station_key','river','station','metric','unit','deduplicated_observations',
               'valid_observations','valid_days','sample_mean','sample_min','sample_max','first_value',
               'last_value','conflicts','missing','note']

def read_json(path):return json.loads(path.read_text('utf-8'))
def atomic_bytes(path,content):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+'.tmp')
    temporary.write_bytes(content);temporary.replace(path)
def dump(path,value):atomic_bytes(path,(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))
def write_csv(path,rows,columns):
    handle=io.StringIO(newline='');writer=csv.DictWriter(handle,fieldnames=columns,extrasaction='ignore');writer.writeheader()
    for row in rows:
        writer.writerow({key:json.dumps(value,ensure_ascii=False,separators=(',',':')) if isinstance(value,(dict,list)) else value for key,value in row.items()})
    atomic_bytes(path,handle.getvalue().encode('utf-8-sig'))

def successful_batches(root):
    batches=[]
    manifests=list((root/'data/daily').glob('*/*/manifest.json'))+list((root/'history/wayback/recovered').glob('*/manifest.json'))
    for manifest_path in sorted(manifests):
        manifest=read_json(manifest_path);data=manifest_path.parent/'water.json';table=manifest_path.parent/'water.csv'
        if manifest.get('status')!='success' or not data.exists() or not table.exists():continue
        records=read_json(data)
        if len(records)!=manifest.get('rows'):raise ValueError('Row count mismatch: '+str(manifest_path))
        batches.append({'captured_at':manifest['started_at'],'manifest':manifest_path.relative_to(root).as_posix(),
                        'json':data,'csv':table,'records':records,
                        'kind':manifest.get('kind','daily_capture')})
    return batches

def combine_metric(items,field):
    variants=sorted({item.get(field) for item in items if item.get(field) is not None})
    if len(variants)>1:return None,'conflict',variants
    if variants:return variants[0],'valid',variants
    return None,'missing',[]

def station_records(root):
    groups=collections.defaultdict(list)
    for batch in successful_batches(root):
        for raw in batch['records']:
            item={**raw,'_manifest':batch['manifest']};groups[(raw['station_key'],raw['observed_at'])].append(item)
    output=[]
    for (key,observed),items in sorted(groups.items()):
        items.sort(key=lambda row:(row['captured_at'],row['_manifest']));last=items[-1]
        row={'station_key':key,'river':last['river'],'station':last['station'],'observed_at':observed,
             'units':last.get('units',{'water_level_value':None,'flow_value':None}),'unit_status':last.get('unit_status','not_stated_on_page'),
             'limit_value_raw':last.get('limit_value_raw'),'limit_value_semantics':last.get('limit_value_semantics'),
             'quality':{},'raw_variants':{},'source_occurrences':len(items),
             'first_captured_at':items[0]['captured_at'],'last_captured_at':last['captured_at'],
             'source_manifests':[item['_manifest'] for item in items],
             'original_fields':{key:value for key,value in last.items() if not key.startswith('_')}}
        for field in METRICS:
            value,status,variants=combine_metric(items,field);row[field]=value
            row['quality'][field]=status;row['raw_variants'][field]=variants
        semantic=sorted({item.get('limit_value_semantics') for item in items})
        if len(semantic)>1:
            row['limit_value_semantics']='conflict';row['quality']['limit_value_number']='conflict';row['limit_value_number']=None
        output.append(row)
    return output

def filename(row):
    safe=''.join('_' if char in '/\\:*?"<>|' or ord(char)<32 else char for char in row['river']+'_'+row['station']).strip(' ._')
    return safe[:72]+'__'+hashlib.sha1(row['station_key'].encode('utf-8')).hexdigest()[:12]

def monthly_rows(records):
    groups=collections.defaultdict(list)
    for row in records:
        month=row['observed_at'][:7]
        for field in METRICS:groups[(month,row['station_key'],field)].append(row)
    output=[];labels={'water_level_value':('water_level',''),'flow_value':('flow',''),'limit_value_number':('below_threshold_difference','')}
    for (month,key,field),items in sorted(groups.items()):
        first=items[0];eligible=[]
        for item in items:
            if field=='limit_value_number' and item['limit_value_semantics']!='difference_below_threshold':continue
            if item['quality'][field]=='valid':eligible.append(item)
        eligible.sort(key=lambda row:row['observed_at']);values=[row[field] for row in eligible]
        output.append({'month':month,'station_key':key,'river':first['river'],'station':first['station'],
                       'metric':labels[field][0],'unit':labels[field][1],
                       'deduplicated_observations':len(items),'valid_observations':len(values),
                       'valid_days':len({row['observed_at'][:10] for row in eligible}),
                       'sample_mean':statistics.fmean(values) if values else None,
                       'sample_min':min(values) if values else None,'sample_max':max(values) if values else None,
                       'first_value':values[0] if values else None,'last_value':values[-1] if values else None,
                       'conflicts':sum(row['quality'][field]=='conflict' for row in items),
                       'missing':sum(row['quality'][field]=='missing' for row in items),
                       'note':'sample statistics only; no interpolation' if field!='limit_value_number' else 'only explicit negative differences; positive mixed-column values excluded'})
    return output

def freshness(records,now):
    stale=future=invalid=0;times=[]
    for row in records:
        try:moment=datetime.datetime.fromisoformat(row['observed_at']).replace(tzinfo=TZ);times.append(moment)
        except (ValueError,TypeError,KeyError):invalid+=1;continue
        age=(now-moment).total_seconds()/3600;stale+=age>48;future+=age<0
    return {'fresh':bool(records) and not(stale or future or invalid),'freshness_as_of':now.isoformat(),
            'stale_threshold_hours':48,'stale_station_rows':stale,'future_station_rows':future,
            'invalid_time_rows':invalid,'observation_min':min(times).isoformat() if times else None,
            'observation_max':max(times).isoformat() if times else None}

def export_daily_views(root,batches,now):
    days={}
    for batch in batches:
        captured=datetime.datetime.fromisoformat(batch['captured_at']).astimezone(TZ);day=captured.date()
        if day not in days or captured>datetime.datetime.fromisoformat(days[day]['captured_at']):days[day]=batch
    for day,batch in sorted(days.items()):
        captured=datetime.datetime.fromisoformat(batch['captured_at']).astimezone(TZ);folder=root/'snapshots'/day.strftime('%Y/%m')
        payload={'captured_at':captured.isoformat(),'timezone':'Asia/Shanghai','source_url':collector.SOURCE,
                 'source_manifest':batch['manifest'],'row_count':len(batch['records']),
                 **freshness(batch['records'],captured),'records':batch['records']}
        dump(folder/(day.isoformat()+'.json'),payload);atomic_bytes(folder/(day.isoformat()+'.csv'),batch['csv'].read_bytes())
        dump(folder/(day.isoformat()+'_clean.json'),collector.clean_rows(batch['records']))
        atomic_bytes(folder/(day.isoformat()+'_clean.csv'),collector.clean_csv_bytes(batch['records']))
    if not batches:return None
    batch=max(batches,key=lambda item:item['captured_at']);captured=datetime.datetime.fromisoformat(batch['captured_at']).astimezone(TZ)
    payload={'captured_at':captured.isoformat(),'timezone':'Asia/Shanghai','source_url':collector.SOURCE,
             'source_manifest':batch['manifest'],'row_count':len(batch['records']),
             **freshness(batch['records'],now),'records':batch['records']}
    current=root/'latest/data.json'
    if current.exists() and datetime.datetime.fromisoformat(read_json(current)['captured_at'])>captured:return read_json(current)
    dump(current,payload);atomic_bytes(root/'latest/data.csv',batch['csv'].read_bytes())
    dump(root/'latest/clean.json',collector.clean_rows(batch['records']))
    atomic_bytes(root/'latest/clean.csv',collector.clean_csv_bytes(batch['records']))
    return payload

def build(root=ROOT,now=None):
    now=now or datetime.datetime.now(TZ);now=now.astimezone(TZ);batches=successful_batches(root);records=station_records(root);monthly=monthly_rows(records)
    groups=collections.defaultdict(list)
    for row in records:groups[row['observed_at'][:7]].append(row)
    index=[]
    for month,rows in sorted(groups.items()):
        folder=root/'data'/month;stations=collections.defaultdict(list)
        for row in rows:stations[row['station_key']].append(row)
        mapping={}
        for key,items in sorted(stations.items()):
            items.sort(key=lambda row:row['observed_at']);name=filename(items[0]);relative=(folder/name).relative_to(root).as_posix()
            mapping['./'+relative]=items;write_csv(folder/(name+'.csv'),items,STATION_COLUMNS)
        dump(folder/'HRC.json',mapping);write_csv(folder/'HRC_clean.csv',collector.clean_rows(rows),collector.CLEAN_COLUMNS)
        stats=[row for row in monthly if row['month']==month];write_csv(folder/'月统计.csv',stats,MONTH_COLUMNS)
        manifest={'month':month,'station_keys':len(stations),'station_time_records':len(rows),'monthly_statistic_rows':len(stats),'csv_columns':STATION_COLUMNS}
        dump(folder/'manifest.json',manifest);index.append(manifest)
    write_csv(root/'data/index.csv',index,['month','station_keys','station_time_records','monthly_statistic_rows'])
    latest=export_daily_views(root,[batch for batch in batches if batch['kind']=='daily_capture'],now)
    issue_counts=collections.Counter(state for row in records for state in row['quality'].values())
    quality={'generated_at':now.isoformat(),'archive_build_success':True,'metric_status_counts':dict(issue_counts),
             'source_batches':len(batches),'station_time_records':len(records),'mixed_column_policy':'negative values are differences; non-negative semantics remain unconfirmed'}
    dump(root/'status/archive_quality.json',quality)
    attempt=read_json(root/'status/latest_attempt.json') if (root/'status/latest_attempt.json').exists() else None
    result={'generated_at':now.isoformat(),'archive_build_success':True,'schedule':'17:00 Asia/Shanghai (09:00 UTC)',
            'month_directories':len(index),'station_files':sum(item['station_keys'] for item in index),
            'station_time_records':len(records),'monthly_statistic_rows':len(monthly),
            'last_collection_attempt':attempt,'latest':{key:value for key,value in (latest or {}).items() if key!='records'},
            'quality_report':'status/archive_quality.json'}
    dump(root/'status/latest.json',result);return result

if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False,indent=2))
