"""Catalog completeness, exact model contracts, provenance and failure retention."""
import collections
import copy
import csv
import json
from pathlib import Path
import shutil
import subprocess

import pytest

import monitor_eclipses as M


@pytest.fixture(scope='module')
def model():
    plan,manifest,objects=M.load_sources()
    catalog=M.catalogs(plan,manifest,objects)
    local=M.local_calculations(plan,manifest)
    return plan,manifest,objects,catalog,local


def isolated_root(tmp_path):
    for name in ['monitor_eclipses.py','eclipse_harness.cjs','source_pins.json','eclipse_plan.json','.nvmrc','eclipses.csv']:
        shutil.copy2(M.BASE/name,tmp_path/name)
    for name in ['vendor','sources','tests/fixtures']:
        shutil.copytree(M.BASE/name,tmp_path/name)
    return tmp_path


def node(script):
    completed=subprocess.run(['node','-e',script],cwd=M.BASE,capture_output=True,text=True,check=True)
    return json.loads(completed.stdout)


def test_catalog_scope_century_counts_and_qualifiers_complete(model):
    plan,manifest,objects,catalog,_=model
    century=M.parse_catalog(objects['SEcat5/SE1901-2000.html'],'solar','1901-2000',manifest['entries']['SEcat5/SE1901-2000.html'])
    assert len(century)==228
    assert collections.Counter(r['global_type'] for r in century)=={'P':78,'A':73,'T':71,'H':6}
    assert {'T-','A-','A+','Pe','Pb'} <= {r['source_type_code'] for r in century}
    lunar=M.parse_catalog(objects['LEcat5/LE1901-2000.html'],'lunar','1901-2000',manifest['entries']['LEcat5/LE1901-2000.html'])
    assert collections.Counter(r['global_type'] for r in lunar)=={'N':83,'P':65,'T':81}
    assert sum(r['source_type_code']=='Nx' for r in lunar)==9
    assert collections.Counter(r['kind'] for r in catalog)=={'solar':454,'lunar':459}
    assert collections.Counter(r['global_type'] for r in catalog if r['kind']=='solar')=={'P':155,'A':146,'T':140,'H':13}
    assert collections.Counter(r['global_type'] for r in catalog if r['kind']=='lunar')=={'N':171,'P':122,'T':166}
    for year in ['1900','2100']:
        assert collections.Counter(r['kind'] for r in catalog if r['catalog_date_td'].startswith(year))=={'solar':2,'lunar':2}
    assert len({r['event_id'] for r in catalog})==913


def test_truncated_catalog_fails_completeness(model):
    _,manifest,objects,_,_=model
    text=objects['SEcat5/SE1901-2000.html']
    # Delete one source catalog row, preserving a superficially valid HTML page.
    lines=text.splitlines();index=next(i for i,x in enumerate(lines) if b'09283' in x and b'1901 May 18' in x)
    del lines[index]
    with pytest.raises(ValueError,match='expected 228'):
        M.parse_catalog(b'\n'.join(lines),'solar','1901-2000',manifest['entries']['SEcat5/SE1901-2000.html'])


def test_fixed_independent_nasa_references_and_complete_local_join(model):
    plan,_,_,catalog,local=model
    result=M.validate(catalog,local,plan,M.read_json(M.BASE/'tests/fixtures/nasa_reference_values.json'))
    assert result['status']=='passed'
    assert not result['failed_checks']
    assert len(local)==len(catalog)
    cases=[c for c in result['checks'] if c['check'].startswith('independent')]
    assert len(cases)>=30
    assert all(c['passed'] for c in cases)
    assert 'No independent lunar numeric-altitude validation' in result['geographic_validation']


def test_reference_error_cannot_silently_pass_or_widen_tolerance(model):
    plan,_,_,catalog,local=model
    altered=copy.deepcopy(local)
    r=next(r for r in altered if r['kind']=='solar' and r['greatest_td'].startswith('2006-03-29'))
    next(c for c in r['contacts'] if c['contact']=='C1')['time_ut1']='2006-03-29T09:30:00'
    result=M.validate(catalog,altered,plan,M.read_json(M.BASE/'tests/fixtures/nasa_reference_values.json'))
    assert result['status']=='failed'
    assert 'independent solar2006 C1' in result['failed_checks']
    assert result['frozen_tolerances']['solar_contact_tolerance_seconds']==30


def test_ut1_date_arithmetic_preserves_previous_and_next_days():
    result=node("""
      const {eventTime}=require('./eclipse_harness.cjs');
      const values=[];
      for(const kind of ['solar','lunar']) {
        const e=[2451545,12,64.1,0,64.1];
        values.push(eventTime(e,-13,kind),eventTime(e,13,kind));
      }
      console.log(JSON.stringify(values));
    """)
    assert result==['1999-12-31T22:58:55.900','2000-01-02T00:58:55.900']*2


def test_real_contacts_retain_dates_across_midnight(model):
    _,_,_,_,local=model
    crossing=[r for r in local if any(c['time_ut1'][:10]!=r['greatest_td'][:10] for c in r['contacts'])]
    assert len(crossing)>50
    for r in crossing:
        contacts=r['contacts']
        assert [c['time_ut1'] for c in contacts]==sorted(c['time_ut1'] for c in contacts)
        elapsed=M.seconds_between(contacts[-1]['time_ut1'],contacts[0]['time_ut1'])
        assert 0<elapsed<24*3600


def test_solar_central_phase_clips_source_below_horizon_sentinels():
    result=node("""
      const {visibleCentralDuration:f}=require('./eclipse_harness.cjs');
      const raw={c2:[-1,2],c3:[1,3]};
      const sunset={c1:[-2,1],c4:[2,2.5],c2:[-1,2],c3:[1,3]};sunset.c3[40]=4;
      const sunrise={c1:[-2,2.75],c4:[2,4],c2:[-1,2],c3:[1,3]};sunrise.c2[40]=4;
      console.log(JSON.stringify([f(raw,sunset,true),f(raw,sunrise,true),f(raw,sunset,false),f({},sunset,true)]));
    """)
    assert result==[1800,900,0,None]


def test_lunar_duration_solver_finds_horizon_crossings_between_contacts():
    result=node("""
      const {lunarPhase}=require('./eclipse_harness.cjs');
      const context={populatecircumstances(e,c){c[5]=(c[1]>=0.123 && c[1]<=1.234)?0:2;}};
      console.log(JSON.stringify(lunarPhase(context,[2451545,12,64.1],0,2)));
    """)
    assert result['full_seconds']==7200
    assert result['visible_seconds']==pytest.approx((1.234-.123)*3600,abs=.11)
    assert len(result['intervals'])==1


def test_absent_lunar_phases_remain_unavailable_and_invisible_events_retained(model):
    plan,_,_,catalog,local=model
    events,contacts,annual=M.tables(catalog,local,plan,M.dt.date(2026,9,6))
    assert len(events)==len(catalog)==913
    assert any(not r['visible'] for r in events)
    for r in events:
        if r['kind']=='lunar' and r['global_type']=='N':
            assert r['full_umbral_duration_seconds'] is None
            assert r['visible_total_duration_seconds'] is None
    assert len(annual)==201*7
    assert all(r['status']=='current model year; includes future scheduled dates' for r in annual if r['year']==2026)
    assert all(r['jerusalem_visible_events']<=r['global_events'] for r in annual)


def test_corrupt_source_and_modified_code_refused(tmp_path):
    root=isolated_root(tmp_path)
    manifest=M.read_json(root/'sources/nasa/manifest.json')
    entry=manifest['entries']['JSEX/program.js'];path=root/'sources/nasa'/entry['object']
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='Corrupt source object'):
        M.load_sources(root)


def test_frozen_plan_and_curated_catalog_hashes_enforced(tmp_path):
    root=isolated_root(tmp_path)
    (root/'eclipses.csv').write_bytes((root/'eclipses.csv').read_bytes()+b'\n')
    with pytest.raises(ValueError,match='Pinned input changed: eclipses.csv'):
        M.load_sources(root)


def test_wrong_node_version_rejected_before_calculation(model):
    plan,manifest,_,_,_=model
    plan=copy.deepcopy(plan);plan['calculation']['node_version']='0.0.0'
    with pytest.raises(ValueError,match='Node 0.0.0 required'):
        M.local_calculations(plan,manifest)


def test_offline_replay_artifact_hashes_and_idempotence(tmp_path):
    root=isolated_root(tmp_path);output=root/'data/eclipses'
    first=M.run_monitor(root,output,'2026-09-06')
    before={p.name:p.read_bytes() for p in output.iterdir()}
    second=M.run_monitor(root,output,'2026-09-06')
    assert before=={p.name:p.read_bytes() for p in output.iterdir()}
    assert first==second
    assert set(first['artifacts'])=={'global_catalog.csv','jerusalem_events.csv','jerusalem_contacts.csv','annual_counts.csv','validation.json','report.md'}
    for name,meta in first['artifacts'].items():
        assert M.digest(before[name])==meta['sha256']
        assert len(before[name])==meta['bytes']
    text=before['report.md'].decode()
    assert 'not exact leap-second-aware UTC' in text
    assert 'solar P = partial' in text
    assert 'No independent lunar numeric-altitude validation' in text


def test_late_report_failure_leaves_previous_snapshot_unchanged(tmp_path,monkeypatch):
    root=isolated_root(tmp_path);output=root/'data/eclipses'
    M.run_monitor(root,output,'2026-09-06')
    before={p.name:p.read_bytes() for p in output.iterdir()}
    def fail(*args): raise ValueError('injected late rendering failure')
    monkeypatch.setattr(M,'report',fail)
    with pytest.raises(ValueError,match='injected late'):
        M.run_monitor(root,output,'2026-09-07')
    assert before=={p.name:p.read_bytes() for p in output.iterdir()}


def test_validation_failure_retains_previous_success_snapshot(tmp_path,monkeypatch):
    root=isolated_root(tmp_path);output=root/'data/eclipses'
    M.run_monitor(root,output,'2026-09-06')
    before={p.name:p.read_bytes() for p in output.iterdir()}
    monkeypatch.setattr(M,'validate',lambda *args:{'status':'failed','failed_checks':['injected']})
    with pytest.raises(ValueError,match='Eclipse validation failed'):
        M.run_monitor(root,output,'2026-09-07')
    assert before=={p.name:p.read_bytes() for p in output.iterdir()}
