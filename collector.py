"""Collect the public realtime water table embedded in the HRC homepage."""
import csv,datetime,io,json,os,pathlib,shutil,time,urllib.request,zipfile
from html.parser import HTMLParser

ROOT=pathlib.Path(__file__).resolve().parent
TZ=datetime.timezone(datetime.timedelta(hours=8))
SOURCE='http://www.hrc.gov.cn/swj/'
HEADERS=['河流','站名','日期','水位','流量','超警戒/汛限水位']
CSV_COLUMNS=['river','station','observed_at','water_level_value','water_level_unit','flow_value','flow_unit','unit_status','limit_value_raw',
             'limit_value_number','limit_value_semantics','water_level_quality','flow_quality',
             'captured_at','source_url']

class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.table=[]
        elif tag=='tr' and self.table is not None:self.row=[]
        elif tag in ('td','th') and self.row is not None:self.cell=[]
        elif tag=='br' and self.cell is not None:self.cell.append(' ')
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()));self.cell=None
        elif tag=='tr' and self.row is not None:
            if self.row:self.table.append(self.row)
            self.row=None
        elif tag=='table' and self.table is not None:
            self.tables.append(self.table);self.table=None

def numeric(raw):
    raw=raw.strip()
    if not raw:return None,'missing'
    try:return float(raw),'valid'
    except ValueError:return None,'invalid'

def classify_limit_value(raw):
    value,status=numeric(raw)
    if status!='valid':return {'limit_value_number':None,'limit_value_semantics':status}
    if value<0:return {'limit_value_number':value,'limit_value_semantics':'difference_below_threshold'}
    if value==0:return {'limit_value_number':value,'limit_value_semantics':'zero_semantics_unconfirmed'}
    return {'limit_value_number':value,'limit_value_semantics':'positive_value_semantics_unconfirmed'}

def parse_water_table(html):
    parser=Tables();parser.feed(html)
    target=None
    for table_index,table in enumerate(parser.tables):
        for index,row in enumerate(table):
            if row==HEADERS:
                target=table[index+1:]
                if not target and table_index+1<len(parser.tables):target=parser.tables[table_index+1]
                break
        if target is not None:break
    if target is None:raise ValueError('Realtime water table with expected headers was not found')
    output=[]
    for cells in target:
        if len(cells)!=6:raise ValueError('Realtime water row has '+str(len(cells))+' cells, expected 6')
        river,station,observed,level,flow,limit=cells
        try:
            moment=datetime.datetime.fromisoformat(observed).replace(tzinfo=TZ)
        except ValueError as error:raise ValueError('Invalid observation time: '+observed) from error
        water,water_quality=numeric(level);discharge,flow_quality=numeric(flow)
        if not river or not station or water_quality!='valid':raise ValueError('Required river, station or water level is invalid')
        output.append({'station_key':'name:'+river+'|'+station,'river':river,'station':station,
                       'observed_at':moment.strftime('%Y-%m-%d %H:%M:%S'),
                       'water_level_value':water,'flow_value':discharge,
                       'units':{'water_level_value':None,'flow_value':None},'unit_status':'not_stated_on_page','limit_value_raw':limit,
                       **classify_limit_value(limit),
                       'quality':{'water_level_value':water_quality,'flow_value':flow_quality}})
    if not output:raise ValueError('Realtime water table is empty')
    return output

def atomic_bytes(path,content):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+'.tmp')
    temporary.write_bytes(content);temporary.replace(path)

def dump_json(path,value):
    atomic_bytes(path,(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))

def csv_bytes(rows):
    handle=io.StringIO(newline='');writer=csv.DictWriter(handle,fieldnames=CSV_COLUMNS,extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow({**row,'water_level_unit':row['units']['water_level_value'],
                         'flow_unit':row['units']['flow_value'],
                         'water_level_quality':row['quality']['water_level_value'],
                         'flow_quality':row['quality']['flow_value']})
    return handle.getvalue().encode('utf-8-sig')

def fetch_url(url):
    error=None
    for attempt in range(3):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 HRC public archive','Accept-Encoding':'identity'})
            with urllib.request.urlopen(request,timeout=45) as response:
                if response.status!=200:raise OSError('HTTP '+str(response.status))
                return response.read()
        except Exception as caught:
            error=caught
            if attempt<2:time.sleep(2**attempt)
    raise RuntimeError('Source download failed: '+str(error))

def pack_evidence(destination,raw):
    files=sorted(path for path in raw.glob('*') if path.is_file())
    if not files:return
    with zipfile.ZipFile(destination/'raw_evidence.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in files:archive.write(path,path.name)

def collect(root=ROOT,fetcher=fetch_url,now=None):
    now=now or datetime.datetime.now(TZ);now=now.astimezone(TZ)
    relative=pathlib.Path('data/daily')/now.strftime('%Y-%m-%d')/now.strftime('%H%M%S_%f')
    destination=root/relative;raw=destination/'raw';raw.mkdir(parents=True,exist_ok=True)
    manifest={'started_at':now.isoformat(),'timezone':'Asia/Shanghai','source_url':SOURCE,
              'scheduled_time':'17:00 Asia/Shanghai',
              'trigger':os.environ.get('GITHUB_EVENT_NAME','local'),
              'github_run_id':os.environ.get('GITHUB_RUN_ID'),
              'snapshot_directory':relative.as_posix(),'status':'failed'}
    try:
        body=fetcher(SOURCE);atomic_bytes(raw/'index.html',body)
        rows=parse_water_table(body.decode('utf-8-sig'))
        for row in rows:row.update(captured_at=now.isoformat(),source_url=SOURCE)
        dump_json(destination/'water.json',rows);atomic_bytes(destination/'water.csv',csv_bytes(rows))
        manifest.update(status='success',rows=len(rows),observation_min=min(row['observed_at'] for row in rows),
                        observation_max=max(row['observed_at'] for row in rows))
        dump_json(destination/'manifest.json',manifest)
        pack_evidence(destination,raw)
        compatibility=root/'data/latest';compatibility.mkdir(parents=True,exist_ok=True)
        for name in ('water.json','water.csv','manifest.json','raw_evidence.zip'):
            shutil.copyfile(destination/name,compatibility/name)
        dump_json(root/'status/latest_success.json',manifest);dump_json(root/'status/latest_attempt.json',manifest)
        return manifest
    except Exception as error:
        pack_evidence(destination,raw)
        manifest.update(status='failed',error=str(error));dump_json(destination/'manifest.json',manifest)
        dump_json(root/'status/latest_attempt.json',manifest)
        raise

if __name__=='__main__':
    result=collect();print(json.dumps(result,ensure_ascii=False,indent=2))
