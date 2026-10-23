"""Registros de mediciones agrícolas independientes del clasificador experimental."""
import csv
import io
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone

SCHEMAS = {
    'families': {'code':'Clave de familia','name':'Nombre de familia','basis':'Origen o criterio de agrupación','notes':'Observaciones'},
    'materials': {'code':'Clave de material','name':'Nombre local o descripción','municipality':'Municipio y estado','locality':'Localidad','family_code':'Familia documentada','sample_id':'Fotografía guardada','notes':'Observaciones'},
    'plots': {'code':'Clave de parcela','material_code':'Material sembrado','season':'Ciclo agrícola','site':'Sitio o localidad','sown_date':'Fecha de siembra','area_m2':'Superficie de parcela (m²)','soil_ph':'pH del suelo','organic_matter_pct':'Materia orgánica (%)','rainfall_mm':'Lluvia acumulada (mm)','notes':'Manejo y observaciones'},
    'observations': {'code':'Clave de observación','plot_code':'Parcela','observed_date':'Fecha de observación','plant_id':'Identificador de planta','height_cm':'Altura medida (cm)','anthesis_date':'Fecha de floración masculina','silking_date':'Fecha de floración femenina','ears_count':'Mazorcas observadas','grain_count':'Granos contados','harvest_kg':'Masa total cosechada (kg)','harvest_area_m2':'Superficie efectivamente cosechada (m²)','moisture_pct':'Humedad medida del grano (%)','reference_moisture_pct':'Humedad de referencia (%)','notes':'Instrumento, método y observaciones'},
    'crosses': {'code':'Clave de cruzamiento','mother_code':'Material parental materno','father_code':'Material parental paterno','status':'Estado del cruzamiento','date':'Fecha de planeación o realización','generation':'Generación','notes':'Objetivo y observaciones'},
}
REQUIRED = {'families': ['code','name','basis'], 'materials':['code','name','municipality','locality'], 'plots':['code','material_code','season','site','sown_date','area_m2'], 'observations':['code','plot_code','observed_date'], 'crosses':['code','mother_code','father_code','status','date']}
NUMBERS = {'area_m2':(0,1e9,False),'harvest_area_m2':(0,1e9,False),'soil_ph':(0,14,True),'organic_matter_pct':(0,100,True),'rainfall_mm':(0,20000,True),'height_cm':(0,1500,False),'ears_count':(0,10000000,True),'grain_count':(0,1000000000,True),'harvest_kg':(0,1e9,True),'moisture_pct':(0,100,True),'reference_moisture_pct':(0,100,True)}
RELATIONS = {'materials':{'family_code':'families'},'plots':{'material_code':'materials'},'observations':{'plot_code':'plots'},'crosses':{'mother_code':'materials','father_code':'materials'}}

@contextmanager
def database(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=15)
    db.execute('CREATE TABLE IF NOT EXISTS agricultural_records (kind TEXT NOT NULL, code TEXT NOT NULL, payload TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY(kind,code))')
    try:
        with db:yield db
    finally:db.close()

def get(db,kind,code):
    row=db.execute('SELECT payload FROM agricultural_records WHERE kind=? AND code=?',(kind,code)).fetchone()
    return json.loads(row[0]) if row else None

def validate(db,kind,payload):
    if kind not in SCHEMAS or not isinstance(payload,dict):raise ValueError('Tipo de registro inválido.')
    if set(payload)-set(SCHEMAS[kind]):raise ValueError('Hay campos no reconocidos en el registro.')
    row={}
    for key,value in payload.items():
        if value is None or value=='':continue
        if key in NUMBERS:
            if isinstance(value,bool):raise ValueError(f'{SCHEMAS[kind][key]} debe ser numérico.')
            try:n=float(value)
            except (ValueError,TypeError):raise ValueError(f'{SCHEMAS[kind][key]} debe ser numérico.')
            lo,hi,inclusive=NUMBERS[key]
            if not math.isfinite(n) or n>hi or (n<lo if inclusive else n<=lo) or (key in ('moisture_pct','reference_moisture_pct') and n>=100):raise ValueError(f'Valor fuera de rango: {SCHEMAS[kind][key]}.')
            if key.endswith('_count') and not n.is_integer():raise ValueError('Los conteos deben ser enteros.')
            row[key]=n
        else:
            if not isinstance(value,str) or len(value)>(2000 if key=='notes' else 300):raise ValueError('Texto inválido o demasiado largo.')
            row[key]=value.strip()
            if key.endswith('_date') or key=='date':
                try:
                    if date.fromisoformat(row[key]).isoformat()!=row[key]:raise ValueError()
                except ValueError:raise ValueError(f'Fecha inválida: {SCHEMAS[kind][key]}.')
    for key in REQUIRED[kind]:
        if key not in row or row[key]=='':raise ValueError(f'Completa {SCHEMAS[kind][key]}.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',row['code']):raise ValueError('La clave admite letras sin acentos, números, guion y guion bajo; máximo 60 caracteres.')
    for key,target in RELATIONS.get(kind,{}).items():
        if row.get(key) and not get(db,target,row[key]):raise ValueError(f'No existe el registro asociado: {SCHEMAS[kind][key]}.')
    if kind=='materials' and row.get('sample_id'):
        try:found=db.execute('SELECT 1 FROM samples WHERE id=? AND deleted=0',(row['sample_id'],)).fetchone()
        except sqlite3.OperationalError:found=None
        if not found:raise ValueError('No existe la fotografía guardada seleccionada.')
    if kind=='crosses':
        if row['mother_code']==row['father_code']:raise ValueError('Selecciona dos parentales distintos. Este registro no representa una autofecundación.')
        if row['status'] not in ('planned','performed'):raise ValueError('Estado del cruzamiento inválido.')
    if kind=='observations':
        plot=get(db,'plots',row['plot_code'])
        for key in ('observed_date','anthesis_date','silking_date'):
            if row.get(key) and row[key]<plot['sown_date']:raise ValueError('La observación o floración no puede ser anterior a la siembra.')
        for key in ('anthesis_date','silking_date'):
            if row.get(key) and row[key]>row['observed_date']:raise ValueError('La floración medida no puede ser posterior a la fecha de observación.')
        has_mass='harvest_kg' in row;has_area='harvest_area_m2' in row
        if has_mass!=has_area:raise ValueError('Para calcular rendimiento registra masa y superficie efectivamente cosechada.')
        if has_area and row['harvest_area_m2']>plot['area_m2']:raise ValueError('La superficie cosechada supera la superficie de la parcela.')
        if ('moisture_pct' in row)!=('reference_moisture_pct' in row):raise ValueError('Registra ambas humedades o deja ambas vacías.')
        if 'moisture_pct' in row and not has_mass:raise ValueError('Las humedades requieren un registro de cosecha.')
    return row

def check_plot_update(db,row):
    for (raw,) in db.execute("SELECT payload FROM agricultural_records WHERE kind='observations'"):
        obs=json.loads(raw)
        if obs['plot_code']!=row['code']:continue
        if min(obs.get(k,'9999-12-31') for k in ['observed_date','anthesis_date','silking_date'])<row['sown_date']:raise ValueError('La nueva siembra contradice fechas de observaciones existentes.')
        if obs.get('harvest_area_m2',0)>row['area_m2']:raise ValueError('La nueva superficie es menor que una cosecha ya registrada.')

def write(db,kind,payload,update=False):
    row=validate(db,kind,payload);old=get(db,kind,row['code'])
    if old and not update:raise FileExistsError('La clave ya existe. Abre el registro para editarlo.')
    if not old and update:raise LookupError('El registro ya no existe.')
    if kind=='plots':check_plot_update(db,row)
    db.execute('INSERT INTO agricultural_records VALUES (?,?,?,?) ON CONFLICT(kind,code) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',(kind,row['code'],json.dumps(row,ensure_ascii=False,allow_nan=False),datetime.now(timezone.utc).isoformat()))
    return row

def derived(db,row):
    result={}
    plot=get(db,'plots',row['plot_code'])
    if not plot:return result
    if 'harvest_kg' in row:
        mass=row['harvest_kg']
        corrected='moisture_pct' in row
        if corrected:mass*= (100-row['moisture_pct'])/(100-row['reference_moisture_pct'])
        result['yield_t_ha']=round(mass*10/row['harvest_area_m2'],5)
        result['yield_basis']=f"Ajustado a {row['reference_moisture_pct']:g} % de humedad" if corrected else 'Masa tal como se cosechó; sin ajuste de humedad'
    for key,name in [('anthesis_date','days_to_anthesis'),('silking_date','days_to_silking')]:
        if row.get(key):result[name]=(date.fromisoformat(row[key])-date.fromisoformat(plot['sown_date'])).days
    return result

def overview(db):
    data={kind:[] for kind in SCHEMAS}
    for kind,code,raw,updated in db.execute('SELECT kind,code,payload,updated FROM agricultural_records ORDER BY code'):
        row=json.loads(raw)
        if kind=='observations':row['derived']=derived(db,row)
        data[kind].append({**row,'updated':updated})
    plots={r['code']:r for r in data['plots']};materials={r['code']:r for r in data['materials']}
    readiness=[]
    for target,label in [('yield_t_ha','Rendimiento medido'),('height_cm','Altura medida'),('days_to_anthesis','Floración masculina'),('days_to_silking','Floración femenina')]:
        rows=[r for r in data['observations'] if (r.get('derived',{}) if target!='height_cm' else r).get(target) is not None]
        pc={r['plot_code'] for r in rows}
        fc={materials.get(plots.get(code,{}).get('material_code'),{}).get('family_code') for code in pc}-{None,''}
        readiness.append({'target':label,'records':len(rows),'plots':len(pc),'families':len(fc)})
    return {'records':data,'readiness':readiness}

def csv_text(db,kind,template=False):
    if kind not in SCHEMAS:raise ValueError('Tipo de registro inválido.')
    output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(SCHEMAS[kind])
    if not template:
        for (raw,) in db.execute('SELECT payload FROM agricultural_records WHERE kind=? ORDER BY code',(kind,)):
            row=json.loads(raw);values=[]
            for key in SCHEMAS[kind]:
                value=row.get(key,'')
                if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):value="'"+value
                values.append(value)
            writer.writerow(values)
    return '\ufeff'+output.getvalue()

def import_csv(db,kind,raw):
    if kind not in SCHEMAS:raise ValueError('Tipo de registro inválido.')
    try:reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    except UnicodeDecodeError:raise ValueError('Usa un CSV UTF-8.')
    if not reader.fieldnames or set(reader.fieldnames)-set(SCHEMAS[kind]) or not set(REQUIRED[kind]).issubset(reader.fieldnames):raise ValueError('Las columnas no coinciden con la plantilla de este registro.')
    count=0
    for i,row in enumerate(reader,2):
        if i>1001:raise ValueError('Importa como máximo 1000 registros por archivo.')
        try:write(db,kind,row)
        except (ValueError,FileExistsError) as exc:raise ValueError(f'Fila {i}: {exc}')
        count+=1
    if not count:raise ValueError('El archivo no tiene registros.')
    return count

def router(path_provider):
    from fastapi import APIRouter,File,UploadFile,HTTPException
    from fastapi.responses import Response
    api=APIRouter(prefix='/api/agriculture')
    @api.get('')
    def records():
        with database(path_provider()) as db:return overview(db)
    @api.get('/{kind}/csv')
    def export(kind:str,template:bool=False):
        try:
            with database(path_provider()) as db:text=csv_text(db,kind,template)
        except ValueError as exc:raise HTTPException(422,str(exc))
        return Response(text,media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="simac_{kind}.csv"'})
    @api.post('/{kind}/import')
    def import_records(kind:str,file:UploadFile=File(...)):
        raw=file.file.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:raise HTTPException(413,'El CSV supera 2 MB.')
        try:
            with database(path_provider()) as db:count=import_csv(db,kind,raw)
        except (ValueError,UnicodeDecodeError) as exc:raise HTTPException(422,str(exc))
        return {'imported':count}
    def persist(kind,payload,update):
        try:
            with database(path_provider()) as db:return write(db,kind,payload,update)
        except FileExistsError as exc:raise HTTPException(409,str(exc))
        except LookupError as exc:raise HTTPException(404,str(exc))
        except ValueError as exc:raise HTTPException(422,str(exc))
    @api.post('/{kind}')
    def create(kind:str,payload:dict):return persist(kind,payload,False)
    @api.put('/{kind}/{code}')
    def update(kind:str,code:str,payload:dict):
        if payload.get('code')!=code:raise HTTPException(422,'La clave de un registro no puede cambiarse.')
        return persist(kind,payload,True)
    return api
