import json
import os
import sqlite3
from pathlib import Path
from app.policy import country, fields_error, name_key, tax_key

def connect():
    path = Path(os.getenv('DATABASE_PATH', 'data/suppliers.db'))
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    return c

def init():
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS suppliers (id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL, tax_id TEXT NOT NULL, status TEXT NOT NULL, name_key TEXT UNIQUE NOT NULL, tax_key TEXT UNIQUE NOT NULL)")
        seed = Path(__file__).resolve().parent.parent / 'data/seed.json'
        for d in json.loads(seed.read_text()):
            c.execute('INSERT OR IGNORE INTO suppliers VALUES (?,?,?,?,?,?,?)', (d['id'], d['name'], d['country'], d['tax_id'], d['status'], name_key(d['name']), tax_key(d['tax_id'])))

def rows(country_filter=None, status=None, name=None, supplier_id=None):
    sql = 'SELECT id,name,country,tax_id,status FROM suppliers WHERE 1=1'
    args=[]
    for col, val in [('country', country_filter), ('status',status), ('id',supplier_id)]:
        if val:
            sql += f' AND {col}=?'; args.append(val)
    if name:
        sql += " AND instr(name_key,?)>0"; args.append(name_key(name))
    with connect() as c:
        return [dict(r) for r in c.execute(sql+' ORDER BY id', args)]

def validate(d):
    error=fields_error(d)
    if error: return {'valid':False, 'reason':error}
    with connect() as c:
        duplicate=c.execute('SELECT id FROM suppliers WHERE name_key=? OR tax_key=?', (name_key(d['name']),tax_key(d['tax_id']))).fetchone()
    return {'valid':not bool(duplicate), 'reason':f"Supplier already exists ({duplicate['id']})." if duplicate else 'Validated.'}

def create(d):
    error=fields_error(d)
    if error: return {'ok':False,'reason':error}
    try:
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            existing=c.execute('SELECT id,name,country,tax_id,status FROM suppliers WHERE name_key=? OR tax_key=?',(name_key(d['name']),tax_key(d['tax_id']))).fetchone()
            if existing:
                # Exact replay resolves an uncertain write without inserting again.
                exact=(name_key(existing['name'])==name_key(d['name']) and existing['country']==d['country'] and tax_key(existing['tax_id'])==tax_key(d['tax_id']))
                return {'ok':exact,'supplier':dict(existing) if exact else None,'reason':'Existing supplier; no additional record created.'}
            prefix={'Kenya':'KE','Uganda':'UG','Tanzania':'TZ'}[d['country']]
            n=c.execute('SELECT count(*) FROM suppliers').fetchone()[0]+1
            sid=f'{prefix}{n:04d}'
            c.execute('INSERT INTO suppliers VALUES (?,?,?,?,?,?,?)',(sid,d['name'].strip(),country(d['country']),tax_key(d['tax_id']),'active',name_key(d['name']),tax_key(d['tax_id'])))
            return {'ok':True,'supplier':{'id':sid,**d,'status':'active'}}
    except sqlite3.IntegrityError:
        return {'ok':False,'reason':'Supplier already exists.'}
