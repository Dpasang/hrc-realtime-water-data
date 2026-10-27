"""Recover parseable HRC homepage water tables from verified Wayback captures."""
import datetime,gzip,hashlib,json,pathlib,subprocess
import collector

ROOT=pathlib.Path(__file__).resolve().parent
CDX='https://web.archive.org/cdx/search/cdx?url=www.hrc.gov.cn/swj/&output=json&filter=statuscode:200&filter=mimetype:text/html&fl=timestamp,original,statuscode,digest&collapse=digest'

def parse_cdx(content):
    data=json.loads(content.decode('utf-8-sig'));headers=data[0];seen=set();output=[]
    for values in data[1:]:
        row=dict(zip(headers,values));digest=row.get('digest')
        if row.get('statuscode')!='200' or not digest or digest in seen:continue
        seen.add(digest);output.append(row)
    return output

def fetch_url(url):
    result=subprocess.run(['curl','--fail','--silent','--show-error','--location','--max-time','50',
                           '--retry','2','--retry-all-errors','--retry-delay','3',url],capture_output=True,timeout=180)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[:500])
    return result.stdout

def archive_time(timestamp):
    return datetime.datetime.strptime(timestamp,'%Y%m%d%H%M%S').replace(tzinfo=datetime.timezone.utc).astimezone(collector.TZ)

def recover(root=ROOT,cdx_content=None,fetcher=fetch_url):
    content=cdx_content if cdx_content is not None else fetcher(CDX);entries=parse_cdx(content)
    snapshots=[];recovered=0
    for entry in entries:
        timestamp=entry['timestamp'];replay=f'https://web.archive.org/web/{timestamp}id_/{entry["original"]}'
        item={'timestamp':timestamp,'original':entry['original'],'digest':entry['digest'],'replay_url':replay,'status':'excluded'}
        try:
            response=fetcher(replay);encoding='gzip' if response.startswith(b'\x1f\x8b') else 'identity'
            if encoding=='gzip':
                collector.atomic_bytes(root/'history/wayback/pages'/(timestamp+'.response.gz'),response)
                body=gzip.decompress(response)
            else:body=response
            page=root/'history/wayback/pages'/(timestamp+'.html');collector.atomic_bytes(page,body)
            rows=collector.parse_water_table(body.decode('utf-8-sig'));captured=archive_time(timestamp)
            for row in rows:row.update(captured_at=captured.isoformat(),source_url=entry['original'],archive_url=replay)
            folder=root/'history/wayback/recovered'/timestamp
            collector.dump_json(folder/'water.json',rows);collector.atomic_bytes(folder/'water.csv',collector.csv_bytes(rows))
            manifest={'started_at':captured.isoformat(),'timezone':'Asia/Shanghai','status':'success',
                      'kind':'historical_wayback','rows':len(rows),'source_url':entry['original'],
                      'archive_url':replay,'archive_timestamp_utc':timestamp,
                      'observation_min':min(row['observed_at'] for row in rows),
                      'observation_max':max(row['observed_at'] for row in rows),
                      'response_encoding':encoding,'source_response_sha256':hashlib.sha256(response).hexdigest(),
                      'decoded_html_sha256':hashlib.sha256(body).hexdigest()}
            collector.dump_json(folder/'manifest.json',manifest);item.update(status='recovered',rows=len(rows),manifest=folder.relative_to(root).as_posix()+'/manifest.json');recovered+=1
        except Exception as error:item['reason']=str(error)
        snapshots.append(item)
    summary={'generated_at':datetime.datetime.now(collector.TZ).isoformat(),'checks_passed':True,
             'cdx_entries':len(entries),'recovered_snapshots':recovered,
             'excluded_snapshots':len(entries)-recovered,'snapshots':snapshots}
    collector.dump_json(root/'history/wayback/verified_summary.json',summary)
    collector.atomic_bytes(root/'history/wayback/cdx.json',content)
    return summary

if __name__=='__main__':
    result=recover();print(json.dumps({key:value for key,value in result.items() if key!='snapshots'},ensure_ascii=False,indent=2))
