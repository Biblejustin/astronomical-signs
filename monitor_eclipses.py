"""Replay pinned NASA eclipse catalogs and fixed Jerusalem model, offline by default.

No Python package dependency for this monitor; Node version is pinned in .nvmrc.
Live source checks stage candidates for review and never replace pinned sources.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

if sys.version_info < (3, 11):
    raise RuntimeError('Eclipse monitor requires Python 3.11+; use the pinned Python 3.13 environment.')

BASE = Path(__file__).resolve().parent
CENTURIES = ['1801-1900', '1901-2000', '2001-2100']
COUNTS = {'solar': [242, 228, 224], 'lunar': [249, 229, 228]}
TYPES = {'solar': ['P', 'A', 'T', 'H'], 'lunar': ['N', 'P', 'T']}
MONTHS = {name: i+1 for i, name in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])}


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()


def read_json(path):
    return json.loads(Path(path).read_text())


class PreText(HTMLParser):
    def __init__(self):
        super().__init__(); self.active=False; self.text=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='pre': self.active=True
    def handle_endtag(self, tag):
        if tag.lower()=='pre': self.active=False; self.text.append('\n')
    def handle_data(self, data):
        if self.active: self.text.append(data)


def optional_number(value):
    return None if value in {'-', ''} else float(value)


def coordinate(value):
    match=re.fullmatch(r'(\d+(?:\.\d+)?)([NSEW])', value)
    if not match: raise ValueError(f'Unexpected geographic coordinate: {value}')
    return float(match[1]) * (-1 if match[2] in 'SW' else 1)


def parse_catalog(payload, kind, century, source):
    parser=PreText(); parser.feed(payload.decode('utf-8', errors='replace'))
    lines=[line for line in ''.join(parser.text).splitlines() if re.match(r'^\s*\d{5}\s+', line)]
    expected=COUNTS[kind][CENTURIES.index(century)]
    if len(lines)!=expected: raise ValueError(f'{kind} {century}: expected {expected} catalog rows; got {len(lines)}')
    rows=[]
    for line in lines:
        fields=line.split()
        if len(fields)<15: raise ValueError('Truncated NASA catalog row')
        date=f'{int(fields[1]):04d}-{MONTHS[fields[2]]:02d}-{int(fields[3]):02d}'
        stamp=dt.datetime.fromisoformat(f'{date}T{fields[4]}')
        year=int(fields[1]); first,last=map(int,century.split('-'))
        if not first<=year<=last: raise ValueError('Catalog century boundary mismatch')
        code=fields[8][0]
        if code not in TYPES[kind]: raise ValueError('Unknown eclipse type')
        row={'event_id':f'{kind}-{fields[0]}', 'kind':kind, 'catalog_number':fields[0],
             'catalog_date_td':date, 'greatest_td':stamp.isoformat(), 'global_type':code,
             'source_type_code':fields[8], 'type_qualifier':fields[8][1:] or None, 'delta_t_seconds':float(fields[5]),
             'greatest_ut1':(stamp-dt.timedelta(seconds=float(fields[5]))).isoformat(),
             'lunation_number':int(fields[6]), 'saros':int(fields[7]), 'quincena':fields[9],
             'gamma_earth_radii':float(fields[10]), 'source_url':source['url'],
             'source_sha256':source['sha256'], 'source_century':century,
             'time_scale':'catalog TD and modeled UT1; not exact UTC', 'source_row':line.strip()}
        if kind=='solar':
            row.update(global_magnitude=float(fields[11]), greatest_latitude_deg=coordinate(fields[12]),
                       greatest_longitude_deg=coordinate(fields[13]), greatest_sun_altitude_deg=float(fields[14]),
                       path_width_km=optional_number(fields[15]) if len(fields)>15 else None,
                       central_duration_seconds=None)
            if len(fields)>16 and fields[16]!='-':
                match=re.fullmatch(r'(\d+)m(\d+)s', fields[16])
                if not match: raise ValueError('Unknown solar duration')
                row['central_duration_seconds']=60*int(match[1])+int(match[2])
        else:
            if len(fields)!=18: raise ValueError('Unexpected lunar catalog row width')
            row.update(penumbral_magnitude=float(fields[11]), umbral_magnitude=float(fields[12]),
                       penumbral_duration_seconds=optional_number(fields[13])*60,
                       umbral_duration_seconds=None if fields[14]=='-' else float(fields[14])*60,
                       total_duration_seconds=None if fields[15]=='-' else float(fields[15])*60,
                       greatest_latitude_deg=coordinate(fields[16]), greatest_longitude_deg=coordinate(fields[17]))
        rows.append(row)
    if len({r['event_id'] for r in rows})!=len(rows): raise ValueError('Duplicate catalog identity')
    return rows


def load_sources(root=BASE):
    root=Path(root); source_root=root/'sources/nasa'; manifest=read_json(source_root/'manifest.json')
    pins=read_json(root/'source_pins.json'); plan=read_json(root/'eclipse_plan.json')
    if not str(plan.get('status','')).startswith('frozen'): raise ValueError('Eclipse plan is not frozen')
    for filename, key in [('eclipse_plan.json','frozen_plan_sha256'),('eclipses.csv','curated_eclipses_sha256'),
                          ('tests/fixtures/nasa_reference_values.json','reference_values_sha256')]:
        if digest((root/filename).read_bytes())!=pins[key]: raise ValueError(f'Pinned input changed: {filename}')
    if set(manifest['entries'])!=set(pins['entries']): raise ValueError('Source manifest membership changed')
    objects={}
    for key, entry in manifest['entries'].items():
        if entry['sha256']!=pins['entries'][key]: raise ValueError(f'Source pin changed: {key}')
        if entry['object']!='objects/'+entry['sha256']: raise ValueError('Unexpected source object path')
        if urlparse(entry['url']).hostname!='eclipse.gsfc.nasa.gov' or not entry['url'].startswith('https://'):
            raise ValueError('Unexpected source origin')
        payload=(source_root/entry['object']).read_bytes()
        if digest(payload)!=entry['sha256'] or len(payload)!=entry['bytes']: raise ValueError(f'Corrupt source object: {key}')
        objects[key]=payload
    for folder in ['JSEX','JLEX']:
        if (root/f'vendor/nasa/{folder}_program.js').read_bytes()!=objects[f'{folder}/program.js']:
            raise ValueError(f'NASA program modified: {folder}')
    if (root/'.nvmrc').read_text().strip()!=plan['calculation']['node_version']: raise ValueError('Node pin differs from frozen plan')
    return plan,manifest,objects


def catalogs(plan, manifest, objects):
    result=[]
    for kind,prefix in [('solar','SE'),('lunar','LE')]:
        for century in CENTURIES:
            key=f'{prefix}cat5/{prefix}{century}.html'
            result.extend(parse_catalog(objects[key],kind,century,manifest['entries'][key]))
    start=plan['scope']['catalog_greatest_td_start']; end=plan['scope']['catalog_greatest_td_end']
    result=[r for r in result if start<=r['catalog_date_td']<=end]
    if len({(r['kind'],r['catalog_date_td']) for r in result})!=len(result): raise ValueError('Ambiguous catalog date join')
    return sorted(result,key=lambda r:(r['catalog_date_td'],r['kind']))


def local_calculations(plan, manifest, root=BASE, node='node'):
    root=Path(root); sources=[]
    for kind,folder,prefix in [('solar','JSEX','SE'),('lunar','JLEX','LE')]:
        for year in [1801,1901,2001]:
            entry=manifest['entries'][f'{folder}/{prefix}{year}.js']
            sources.append({'kind':kind,'program':str(root/f'vendor/nasa/{folder}_program.js'),
                'elements':str(root/'sources/nasa'/entry['object']),'entrypoint':f'{prefix}{year}'})
    request={'node_version':plan['calculation']['node_version'],'location':plan['location'],
        'start':plan['scope']['catalog_greatest_td_start'],'end':plan['scope']['catalog_greatest_td_end'],'sources':sources}
    process=subprocess.run([node,str(root/'eclipse_harness.cjs')],input=json.dumps(request),capture_output=True,text=True,timeout=60)
    if process.returncode: raise ValueError('NASA harness failed: '+process.stderr.strip())
    return json.loads(process.stdout)


def seconds_between(a,b):
    return (dt.datetime.fromisoformat(a)-dt.datetime.fromisoformat(b)).total_seconds()


def validate(catalog, local, plan, references):
    failures=[]; checks=[]
    def check(name, success, **evidence):
        row={'check':name,'passed':bool(success),**evidence}; checks.append(row)
        if not success: failures.append(name)
    key=lambda r:(r['kind'],r.get('catalog_date_td',r.get('greatest_td','')[:10]))
    expected={key(r):r for r in catalog}; actual={key(r):r for r in local}
    check('global event join completeness',len(actual)==len(local)==len(expected) and set(actual)==set(expected),
          catalog_events=len(expected),local_events=len(local))
    for identity, row in actual.items():
        if identity not in expected: continue
        source=expected[identity]
        check(f'{identity} greatest TD alignment',abs(seconds_between(row['greatest_td'],source['greatest_td']))<1.1)
        check(f'{identity} '+('solar local geometry type code' if row['kind']=='solar' else 'lunar element/global catalog type agreement'),
              row['local_geometry_type'] in (['P','A','T','none'] if row['kind']=='solar' else [source['global_type']]))
        for contact in row['contacts']:
            check(f'{identity} {contact["contact"]} altitude finite',contact['altitude_deg'] is not None and math.isfinite(contact['altitude_deg']) and -90<=contact['altitude_deg']<=90)
        times=[c['time_ut1'] for c in row['contacts']]
        check(f'{identity} contact chronology',times==sorted(times) and len(times)==len(set(times)))
        if row['kind']=='solar':
            for label in ['partial','central']:
                total=row[f'full_local_{label}_duration_seconds']; visible=row[f'visible_{label}_duration_seconds']
                check(f'{identity} solar {label} duration bounds',
                      (total is None and visible in [None,0]) or (total is not None and 0<=visible<=total+1))
            if row['visible']:
                check(f'{identity} solar magnitude and obscuration',row['local_magnitude']>0 and row['local_obscuration'] is not None and 0<=row['local_obscuration']<=1)
        else:
            for phase, stats in row['phases'].items():
                check(f'{identity} lunar {phase} duration bounds',0<=stats['visible_seconds']<=stats['full_seconds']+0.1)
                catalog_duration=source[f'{phase}_duration_seconds']
                check(f'{identity} lunar {phase} catalog duration',catalog_duration is not None and abs(stats['full_seconds']-catalog_duration)<=plan['validation']['lunar_contact_duration_tolerance_seconds'],
                      model_seconds=stats['full_seconds'],catalog_seconds=catalog_duration)
    solar=references['solar']; row=actual.get(('solar',solar['date']))
    if row:
        contact={c['contact']:c for c in row['contacts']}
        for name,clock in solar['contacts'].items():
            delta=abs(seconds_between(contact[name]['time_ut1'],solar['date']+'T'+clock))
            check('independent solar2006 '+name,delta<=plan['validation']['solar_contact_tolerance_seconds'],difference_seconds=delta,source_key=solar['source_key'])
        for observed,target,tolerance in [('local_maximum_altitude_deg','maximum_altitude_deg','solar_altitude_tolerance_deg'),
                                           ('local_magnitude','magnitude','solar_magnitude_obscuration_tolerance'),
                                           ('local_obscuration','obscuration','solar_magnitude_obscuration_tolerance')]:
            delta=abs(row[observed]-solar[target]);check('independent solar2006 '+target,delta<=plan['validation'][tolerance],difference=delta,source_key=solar['source_key'])
        check('independent solar2006 local type',row['local_visible_type']==solar['local_type'])
    else: check('independent solar2006 available',False)
    for ref in references['lunar']:
        row=actual.get(('lunar',ref['date']))
        if not row: check('independent lunar '+ref['date']+' available',False);continue
        contact={c['contact']:c for c in row['contacts']}
        for name,clock in ref['contacts'].items():
            delta=abs(seconds_between(contact[name]['time_ut1'],ref['date']+'T'+clock))
            check(f'independent lunar {ref["date"]} {name}',delta<=plan['validation']['lunar_contact_duration_tolerance_seconds'],difference_seconds=delta,source_key=ref['source_key'])
        for phase,total in ref['duration_seconds'].items():
            delta=abs(row['phases'][phase]['full_seconds']-total)
            check(f'independent lunar {ref["date"]} {phase} duration',delta<=plan['validation']['lunar_contact_duration_tolerance_seconds'],difference_seconds=delta,source_key=ref['source_key'])
        for flag,names in [(True,ref['above_horizon_contacts']),(False,ref['below_horizon_contacts'])]:
            for name in names: check(f'independent lunar map {ref["date"]} {name}',contact[name]['above_model_horizon']==flag,source_key=ref['source_key'])
    return {'schema_version':1,'status':'passed' if not failures else 'failed','check_count':len(checks),
            'failed_checks':failures,'checks':checks,'interpretation':plan['validation']['local_validation_limit'],
            'frozen_tolerances':plan['validation'],
            'solar_global_type_validation':'Pinned catalog raw type, normalized type counts and unique greatest-TD identity join only. Solar numeric elements contain no categorical global P/A/T/H field; independent element/global type agreement applies to lunar only.',
            'geographic_validation':'One independent published Jerusalem solar case; three lunar contact/qualitative-map cases. No independent lunar numeric-altitude validation.'}


def tables(catalog, local, plan, as_of):
    lookup={(r['kind'],r['greatest_td'][:10]):r for r in local}; events=[];contacts=[]
    for source in catalog:
        row=lookup[(source['kind'],source['catalog_date_td'])]
        event={k:source[k] for k in ['event_id','kind','catalog_date_td','global_type']}
        event.update({k:v for k,v in row.items() if k not in {'contacts','phases'}})
        event.update(location_id=plan['location']['id'],time_scale='modeled UT1; not exact UTC',
                     prediction_status='future model prediction' if source['catalog_date_td']>str(as_of) else 'past model prediction; not a sighting record')
        for phase in ['penumbral','umbral','total']:
            stats=row.get('phases',{}).get(phase)
            event[f'full_{phase}_duration_seconds']=stats['full_seconds'] if stats else None
            event[f'visible_{phase}_duration_seconds']=stats['visible_seconds'] if stats else None
            event[f'visible_{phase}_intervals_ut1']=json.dumps(stats['intervals']) if stats else None
        events.append(event)
        for contact in row['contacts']:
            contacts.append({'event_id':source['event_id'],'kind':source['kind'], 'catalog_date_td':source['catalog_date_td'],
                'location_id':plan['location']['id'],'time_scale':'modeled UT1; not exact UTC',**contact})
    annual=[]
    for year in range(1900,2101):
        for kind,types in TYPES.items():
            selected=[r for r in events if r['kind']==kind and r['catalog_date_td'].startswith(str(year))]
            for code in types:
                matching=[r for r in selected if r['global_type']==code]
                annual.append({'year':year,'kind':kind,'global_type':code,'global_events':len(matching),
                    'jerusalem_visible_events':sum(r['visible'] for r in matching),
                    'visibility_denominator':'all global events of this source type/year; fixed Jerusalem point',
                    'status':'future model year' if year>as_of.year else 'current model year; includes future scheduled dates' if year==as_of.year else 'past modeled year'})
    return events,contacts,annual


def write_csv(path, rows, fallback):
    fields=list(dict.fromkeys(k for row in rows for k in row)) or fallback
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    path.write_text(stream.getvalue())


def report(catalog,events,validation,plan,as_of):
    lines=['# NASA eclipse monitor','',f'As of {as_of}. Complete modeled catalog for 1900–2100; one fixed Jerusalem point at 31°46′N, 35°14′E, source elevation 808.9 m. '
           'This point does not describe all-Israel visibility. Original selected historical CSV remains separate.','',
           '| Model family | Global catalog events | Jerusalem-visible geometry |', '|---|---:|---:|']
    for kind in TYPES:
        group=[r for r in events if r['kind']==kind]
        lines.append(f'| {kind.title()} | {len(group)} | {sum(r["visible"] for r in group)} |')
    lines += ['', 'Model snapshots: solar canon elements published October 2006; NASA JSEX program version 1 (2007); lunar elements April 2007; NASA JLEX program version 1 (23 May 2007).', '', 'Type codes: solar P = partial, A = annular, T = total, H = hybrid; lunar N = penumbral, P = partial, T = total.', '', 'Counts include future predictions through 2100 and are not a record of human sightings. Visibility means the source model’s horizon criterion is met during at least part of a phase. '
              'Clouds, buildings, terrain, extinction and visual contrast are not modeled. Penumbral geometry does not guarantee naked-eye detection.','',
              '## Upcoming Jerusalem-visible geometry','',
              '| Kind / global → local type | Catalog date (TD) | Visible start → end (UT1) | Maximum time (UT1) / altitude | Above-horizon phase durations |',
              '|---|---|---|---|---|']
    upcoming=sorted((r for r in events if r['visible'] and r['visible_end_ut1'][:10]>=str(as_of)),key=lambda r:r['visible_start_ut1'])[:10]
    for row in upcoming:
        if row['kind']=='solar':
            durations=f'partial {row["visible_partial_duration_seconds"]/60:.1f} min'
            if row['visible_central_duration_seconds'] is not None: durations+=f'; central {row["visible_central_duration_seconds"]/60:.1f} min'
        else:
            durations='; '.join(f'{p} {row[f"visible_{p}_duration_seconds"]/60:.1f} min' for p in ['penumbral','umbral','total'] if row[f'visible_{p}_duration_seconds'] is not None)
        maximum=f'{row["local_maximum_ut1"][:19]} / {row["local_maximum_altitude_deg"]:.1f}°'
        if row['kind']=='lunar' and not row['maximum_above_model_horizon']:maximum+=' (below horizon)'
        lines.append(f'| {row["kind"]} {row["global_type"]} → {row["local_visible_type"]} | {row["catalog_date_td"]} | {row["visible_start_ut1"][:19]} → {row["visible_end_ut1"][:19]} | {maximum} | {durations} |')
    if not upcoming: lines.append('| No further visible geometry within catalog coverage | — | — | — | — |')
    lines += ['', 'UT1 is calculated from source TD minus source ΔT. These timestamps are not exact leap-second-aware UTC. Gregorian dates and timezone 0 are used; contacts retain their own dates across midnight. '
              'Future Earth-rotation uncertainty and the original ephemeris model limit timing accuracy. Decimal output is computational precision, not a timing guarantee.','',
              'Solar horizons retain NASA’s −0.00524 radian threshold and sunrise/sunset clipping. Lunar horizons retain NASA’s parallax/semidiameter/refraction convention; '
              'small negative visible lunar altitudes are reported as 0 by the source, and its simplified lunar altitude formula does not use elevation. '
              'Lunar maximum means global greatest eclipse, which can occur below the local horizon; solar maximum is source horizon-clipped local maximum.','',
              '## Validation and provenance','',f'Validation: **{validation["status"]}**, {validation["check_count"]:,} checks. '
              +validation['geographic_validation'], '', validation['solar_global_type_validation'], '',
              'Source programs are unmodified, GPLv2-or-later NASA Eclipse Explorer code. Source bytes, versions, hashes, reference pages and the frozen plan are pinned for offline replay. '
              'A changed source or failed validation prevents snapshot promotion. Live source checks create review candidates separately.','',
              'Eclipse Predictions by Fred Espenak and Jean Meeus (NASA’s GSFC); local Eclipse Explorer predictions by Fred Espenak and Chris O’Byrne (NASA’s GSFC).','',
              '[Pinned raw source archive](https://github.com/Biblejustin/astronomical-signs/tree/main/sources/nasa) · '
              '[Solar catalog](https://eclipse.gsfc.nasa.gov/SEcat5/SEcatalog.html) · [Lunar catalog](https://eclipse.gsfc.nasa.gov/LEcat5/LEcatalog.html) · '
              '[Solar local model](https://eclipse.gsfc.nasa.gov/JSEX/JSEX-key.html) · [Lunar local model](https://eclipse.gsfc.nasa.gov/JLEX/JLEX-key.html)']
    return '\n'.join(lines)+'\n'


def run_monitor(root=BASE,output=None,as_of=None,node='node'):
    root=Path(root); output=Path(output or root/'data/eclipses')
    day=dt.date.fromisoformat(str(as_of)) if as_of else dt.datetime.now(ZoneInfo('America/Chicago')).date()
    bound_files=['monitor_eclipses.py','eclipse_harness.cjs','source_pins.json','eclipse_plan.json',
                 'sources/nasa/manifest.json','.nvmrc','tests/fixtures/nasa_reference_values.json']
    initial_hashes={name:digest((root/name).read_bytes()) for name in bound_files}
    plan,manifest,objects=load_sources(root); catalog=catalogs(plan,manifest,objects)
    local=local_calculations(plan,manifest,root,node)
    validation=validate(catalog,local,plan,read_json(root/'tests/fixtures/nasa_reference_values.json'))
    if validation['status']!='passed':
        failure=root/'data/diagnostics/eclipse_validation_failure.json';failure.parent.mkdir(parents=True,exist_ok=True)
        failure.write_bytes(json_bytes(validation))
        raise ValueError(f'Eclipse validation failed: {len(validation["failed_checks"])} checks; {failure}')
    events,contacts,annual=tables(catalog,local,plan,day)
    metadata={'schema_version':1,'as_of':str(day),'status':'validated pinned model snapshot',
        'catalog_start_td':plan['scope']['catalog_greatest_td_start'],'catalog_end_td':plan['scope']['catalog_greatest_td_end'],
        'global_events':len(catalog),'jerusalem_visible_events':sum(r['visible'] for r in events),
        'contact_rows':len(contacts),'location':plan['location'],'time':plan['time'],
        'calculation':plan['calculation'],'validation_status':validation['status'],
        'source_model_versions':{'solar_elements':'NASA/TP-2006-214141, October 2006',
            'solar_program':'JSEX Version 1, 2007', 'lunar_elements':'Espenak and Meeus, April 2007',
            'lunar_program':'JLEX Version 1, 23 May 2007'},
        'source_manifest_sha256':digest(json_bytes(manifest)), 'source_pins_sha256':digest((root/'source_pins.json').read_bytes()),
        'plan_sha256':digest((root/'eclipse_plan.json').read_bytes()),'harness_sha256':digest((root/'eclipse_harness.cjs').read_bytes()),
        'driver_sha256':digest((root/'monitor_eclipses.py').read_bytes()),
        'curated_eclipses_sha256':digest((root/'eclipses.csv').read_bytes()),
        'source_urls':{k:v['url'] for k,v in manifest['entries'].items()},
        'interpretation':plan['scope']['interpretation']}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.eclipse-staging-',dir=output.parent) as temp:
        staged=Path(temp)
        for name,rows in [('global_catalog',catalog),('jerusalem_events',events),('jerusalem_contacts',contacts),('annual_counts',annual)]:
            write_csv(staged/(name+'.csv'),rows,['event_id'])
        (staged/'validation.json').write_bytes(json_bytes(validation))
        (staged/'report.md').write_text(report(catalog,events,validation,plan,day))
        metadata['artifacts']={path.name:{'sha256':digest(path.read_bytes()),'bytes':path.stat().st_size} for path in sorted(staged.iterdir())}
        (staged/'monitor.json').write_bytes(json_bytes(metadata))
        # Fail if any pinned live source changed during the calculation.
        _,after,_=load_sources(root)
        if json_bytes(after)!=json_bytes(manifest): raise ValueError('Source manifest changed during run')
        if any(digest((root/name).read_bytes())!=sha for name,sha in initial_hashes.items()):
            raise ValueError('Bound code or source metadata changed during run')
        output.mkdir(parents=True,exist_ok=True)
        for path in sorted(staged.iterdir(),key=lambda p:p.name=='monitor.json'):
            target=output/path.name
            if not target.exists() or target.read_bytes()!=path.read_bytes(): path.replace(target)
    return metadata


def check_live_sources(root=BASE,candidate_dir=None):
    """Fetch candidates for explicit review; pinned inputs never change here."""
    root=Path(root);_,manifest,_=load_sources(root)
    destination=Path(candidate_dir or root/'.cache/eclipse-source-candidates');destination.mkdir(parents=True,exist_ok=True)
    report={'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'sources':[],'active_snapshot_unchanged':True}
    for key,entry in manifest['entries'].items():
        error=None
        for attempt in range(3):
            try:
                with urlopen(entry['url'],timeout=30) as response:payload=response.read()
                if not payload: raise ValueError('Empty source response')
                error=None;break
            except Exception as exc:error=str(exc);time.sleep(attempt+1)
        if error:
            report['sources'].append({'key':key,'status':'fetch failed','error':error});continue
        sha=digest(payload);(destination/sha).write_bytes(payload)
        report['sources'].append({'key':key,'url':entry['url'],'sha256':sha,'pinned_sha256':entry['sha256'],
                                 'status':'unchanged' if sha==entry['sha256'] else 'changed; review required'})
    path=destination/(digest(json_bytes(report))+'.json');path.write_bytes(json_bytes(report))
    return report,path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true',help='Explicit offline replay (also default).')
    parser.add_argument('--check-sources',action='store_true',help='Stage live source candidates for review; no active promotion.')
    parser.add_argument('--candidate-dir',type=Path)
    parser.add_argument('--as-of',help='Report calendar date, YYYY-MM-DD; default America/Chicago today.')
    parser.add_argument('--output',type=Path,default=BASE/'data/eclipses')
    parser.add_argument('--node',default='node')
    args=parser.parse_args()
    if args.check_sources:
        if args.offline:parser.error('--offline and --check-sources are exclusive')
        result,path=check_live_sources(candidate_dir=args.candidate_dir)
        print(f'Candidate review: {path}; active inputs unchanged')
        if any(r['status']!='unchanged' for r in result['sources']):raise SystemExit(2)
    else:
        result=run_monitor(output=args.output,as_of=args.as_of,node=args.node)
        print(f'{result["global_events"]} global events; {result["jerusalem_visible_events"]} visible from fixed Jerusalem point; validation {result["validation_status"]}')


if __name__=='__main__':main()
