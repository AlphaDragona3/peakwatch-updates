"""Read GeneMapper labelled tab-separated panels/bins and explicit CSV tables.
Unknown/ambiguous rows fail the whole import; do not infer missing ranges.
"""
import csv, io, json, math
from pathlib import Path

class PanelError(ValueError):pass

def text_file(path):
    blob=Path(path).read_bytes()
    if len(blob)>10*1024*1024:raise PanelError('Файл 10 MB-аас том байна.')
    encs=['utf-16'] if blob.startswith((b'\xff\xfe',b'\xfe\xff')) else ['utf-8-sig','cp949','cp1252']
    for enc in encs:
        try:
            text=blob.decode(enc)
            if '\x00' in text:raise PanelError('Текст файл биш байна.')
            return text
        except UnicodeDecodeError:continue
    raise PanelError('Файлын кодчилол танигдсангүй.')

def norm(s):return ''.join(c for c in s.lower() if c.isalnum())

def num(s,field):
    try:v=float(s.strip().replace(',','.'))
    except (ValueError,AttributeError):raise PanelError(field+': тоо буруу')
    if not math.isfinite(v) or v<0:raise PanelError(field+': тоо буруу')
    return v

def key(kit,panel,name):return json.dumps([kit,panel,name],ensure_ascii=False,separators=(',',':'))

def label(record):return ' / '.join([record['kit'],record['panel'],record['marker_name']])

def marker(kit,panel,name,dye,lo,hi,repeat='',stutter='',control='',comments='',source=''):
    if not kit or not panel or not name:raise PanelError('Kit, Panel, Marker нэр дутуу.')
    colors={'blue':'Blue','green':'Green','yellow':'Yellow','red':'Red','purple':'Purple','orange':'Orange'}
    if dye.lower() not in colors:raise PanelError(name+': Dye Color танигдсангүй: '+dye)
    lo,hi=num(lo,'Min bp'),num(hi,'Max bp')
    if lo>=hi:raise PanelError(name+': Min bp нь Max bp-ээс бага байх ёстой.')
    return {'kit':kit,'panel':panel,'marker_name':name,'dye':colors[dye.lower()],
            'min_bp':lo,'max_bp':hi,'repeat_type_raw':repeat,'stutter_ratio_raw':stutter,
            'control_alleles_raw':control,'comments':comments,'source_file':source,
            'min_rfu':None,'max_rfu':None,'bins':[]}

def rows_of(text):
    delimiter='\t' if '\t' in text else ','
    return [(i,[v.strip() for v in row]) for i,row in enumerate(csv.reader(io.StringIO(text),delimiter=delimiter),1)
            if any(v.strip() for v in row) and not (row and row[0].lstrip().startswith('#'))]

def read_panels(path):
    rows=rows_of(text_file(path));result={};kit='';panel='';header=None;source=Path(path).name
    for line,c in rows:
        while c and not c[0]:c=c[1:]
        if not c:continue
        tag=norm(c[0]); val=c[1] if len(c)>1 else ''
        try:
            names=[norm(x) for x in c]
            if 'markername' in names and any(x in names for x in ('minsize','minbp','minasr')):
                header={n:i for i,n in enumerate(names)};continue
            if tag in ('version','chemistry','datatype','analysissoftware','kitversion'):continue
            if tag in ('chemistrykit','kitname','kit'):kit=val;panel='';header=None;continue
            if tag in ('panelname','panel'):panel=val;header=None;continue
            if tag in ('binsetname','markername') and len(c)==2:raise PanelError('Энэ Bin файл байж болно; Bin оруулах товч ашиглана уу.')
            names=[norm(x) for x in c]
            if 'markername' in names and any(x in names for x in ('minsize','minbp','minasr')):
                header={n:i for i,n in enumerate(names)};continue
            if header is not None:
                def get(*aliases,default=''):
                    idx=next((header[a] for a in aliases if a in header),None)
                    return c[idx] if idx is not None and idx<len(c) else default
                rec=marker(get('kitname','chemistrykit','kit',default=kit),get('panelname','panel',default=panel),
                    get('markername','marker'),get('dyecolor','dye'),get('minsize','minbp','minasr'),get('maxsize','maxbp','maxasr'),
                    get('markerrepeat','markerrepeattype','repeattype'),get('markerspecificstutterratio','stutterratio'),
                    get('controlalleles'),get('comments'),source)
            elif len(c)>=4 and c[1].lower() in ('blue','green','yellow','red','purple','orange'):
                c=c+['']*max(0,8-len(c));rec=marker(kit,panel,c[0],c[1],c[2],c[3],c[5],c[6],c[4],c[7],source)
            else:raise PanelError('Танигдаагүй мөр. Labelled TXT эсвэл баганын нэртэй CSV/TSV шаардлагатай.')
            ident=label(rec)
            if ident in result:raise PanelError('Нэг Kit/Panel-д Marker нэр давхардсан.')
            result[ident]=rec
        except PanelError as exc:raise PanelError(f'{source}, мөр {line}: {exc}')
    if not result:raise PanelError('Маркер олдсонгүй.')
    return result

def read_bins(path):
    kit=panel=marker_name=binset='';result={};source=Path(path).name
    for line,c in rows_of(text_file(path)):
        while c and not c[0]:c=c[1:]
        tag=norm(c[0]);val=c[1] if len(c)>1 else ''
        try:
            if tag=='version':continue
            if tag in ('chemistrykit','kitname','kit'):kit=val;panel=marker_name='';continue
            if tag in ('binsetname','binset'):binset=val;continue
            if tag in ('panelname','panel'):panel=val;marker_name='';continue
            if tag in ('markername','marker'):marker_name=val;continue
            if len(c)<4 or not all((kit,panel,marker_name,binset)):raise PanelError('Kit/Panel/Marker/BinSet бүтэц дутуу.')
            center,left,right=num(c[1],'Bin center'),num(c[2],'Left offset'),num(c[3],'Right offset')
            ident=' / '.join((kit,panel,marker_name));bucket=result.setdefault(ident,{'binset':binset,'bins':[]})
            if bucket['binset']!=binset:raise PanelError('Нэг маркерт олон BinSet байна; нэгийг нь тусад нь экспортлоно уу.')
            if any(b['name']==c[0] for b in bucket['bins']):raise PanelError('Bin нэр давхардсан.')
            bucket['bins'].append({'name':c[0],'center':center,'left_offset':left,'right_offset':right})
        except PanelError as exc:raise PanelError(f'{source}, мөр {line}: {exc}')
    if not result:raise PanelError('Bin олдсонгүй.')
    return result

def overlaps(records):
    values=list(records.values());notes=[]
    for i,a in enumerate(values):
        for b in values[i+1:]:
            if all(a.get(k)==b.get(k) for k in ('kit','panel','dye')) and max(a['min_bp'],b['min_bp'])<=min(a['max_bp'],b['max_bp']):
                notes.append(f"{a['marker_name']} ↔ {b['marker_name']}: {a['dye']} bp хүрээ давхцаж байна.")
    return notes
