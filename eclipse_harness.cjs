/* SPDX-License-Identifier: GPL-2.0-or-later
 * Adapter for unmodified NASA/GSFC JSEX and JLEX source algorithms.
 * Eclipse Predictions by Fred Espenak and Chris O'Byrne (NASA's GSFC).
 */
'use strict';
const fs = require('node:fs');
const vm = require('node:vm');

function documentFor(location) {
  const scalar = value => ({value});
  const option = value => ({options: [{value}], selectedIndex: 0});
  return {
    eclipseform: {
      latd: scalar(location.latitude_deg_north), latm: scalar(0), lats: scalar(0), latx: option(1),
      lond: scalar(location.longitude_deg_east), lonm: scalar(0), lons: scalar(0), lonx: option(-1),
      alt: scalar(location.elevation_m), tzh: option(0), tzm: option(0), tzx: option(1),
      ecltype: [{checked:true, value:3}, {checked:false, value:2}, {checked:false, value:1}],
    },
    createTextNode: value => ({textContent: String(value)}),
    createElement: () => ({textContent: '', setAttribute(){}, appendChild(node){this.textContent += node.textContent;}}),
  };
}

function load(program, elementsFile, entrypoint, location) {
  const context = vm.createContext({document: documentFor(location), self: {}});
  vm.runInContext(fs.readFileSync(program, 'utf8'), context, {timeout: 1000, filename: program});
  // Only intercept browser rendering/loading. Astronomy functions stay unchanged.
  context.recalculate = () => {};
  context.calculatefor = array => {context.elements = array;};
  vm.runInContext(fs.readFileSync(elementsFile, 'utf8'), context, {timeout: 1000, filename: elementsFile});
  vm.runInContext(`${entrypoint}(); readform();`, context, {timeout: 1000});
  return context;
}

function dateAt(jd) {
  return new Date(Math.round((jd - 2440587.5) * 86400000)).toISOString().replace('Z','');
}

function eventTime(elements, t, kind) {
  // Source JD is the greatest-eclipse TD instant; T0 uses its containing day.
  const base = Math.floor(elements[0] - elements[1]/24) + 0.5;
  const delta = kind === 'solar' ? elements[4] : elements[2];
  return dateAt(base + (elements[1] + t - delta/3600)/24);
}

function visibleCentralDuration(raw, context, visible) {
  if (!raw.c2) return null;
  if (!visible) return 0;
  // NASA can leave C2/C3's physical time below the horizon with flag4.
  // Intersect physical central contacts with the clipped visible interval.
  return Math.max(0, Math.min(raw.c3[1], context.c4[1]) - Math.max(raw.c2[1], context.c1[1]))*3600;
}

function solar(context, elements) {
  context.obsvconst[6] = 0;
  context.c1 = []; context.c2 = []; context.mid = []; context.c3 = []; context.c4 = [];
  context.getmid(elements); context.midobservational();
  const raw = {};
  let physicalType = 'none';
  if (context.mid[37] > 0) {
    context.getc1c4(elements);
    physicalType = Math.abs(context.mid[29]) > context.mid[36] ? (context.mid[29] < 0 ? 'T' : 'A') : 'P';
    context.mid[39] = {P:1,A:2,T:3}[physicalType];
    if (physicalType !== 'P') context.getc2c3(elements);
    for (const name of ['c1','c2','mid','c3','c4']) {
      if ((name === 'c2' || name === 'c3') && physicalType === 'P') continue;
      context.observational(context[name]); raw[name] = Array.from(context[name]);
    }
  }
  context.getall(elements);
  const visible = context.mid[39] > 0;
  const contacts = Object.entries(raw).map(([name, a]) => ({
    contact: name.toUpperCase(), time_ut1: eventTime(elements, a[1], 'solar'),
    offset_hours: a[1], altitude_deg: a[32]*180/Math.PI,
    above_model_horizon: a[40] === 0, source_visibility_flag: a[40],
  }));
  let coverage = null;
  if (visible) coverage = Number.parseFloat(context.getcoverage().textContent);
  return {
    greatest_td: dateAt(elements[0]), delta_t_seconds: elements[4],
    local_geometry_type: physicalType, local_visible_type: visible ? ({1:'P',2:'A',3:'T'}[context.mid[39]]) : 'none',
    visible, contacts,
    local_maximum_ut1: visible ? eventTime(elements, context.mid[1], 'solar') : null,
    local_maximum_altitude_deg: visible ? context.mid[32]*180/Math.PI : null,
    local_maximum_azimuth_deg: visible ? (context.mid[35]*180/Math.PI + 360)%360 : null,
    local_magnitude: visible ? context.mid[37] : null,
    local_obscuration: coverage,
    full_local_partial_duration_seconds: raw.c1 ? (raw.c4[1]-raw.c1[1])*3600 : null,
    visible_partial_duration_seconds: visible ? (context.c4[1]-context.c1[1])*3600 : 0,
    full_local_central_duration_seconds: raw.c2 ? (raw.c3[1]-raw.c2[1])*3600 : null,
    visible_central_duration_seconds: visibleCentralDuration(raw,context,visible),
    visible_start_ut1: visible ? eventTime(elements, context.c1[1], 'solar') : null,
    visible_end_ut1: visible ? eventTime(elements, context.c4[1], 'solar') : null,
    maximum_at_horizon_flag: visible ? context.mid[40] : null,
  };
}

function lunarPhase(context, elements, start, end) {
  function above(t) {
    const circumstance = [0,t]; context.populatecircumstances(elements, circumstance);
    return circumstance[5] === 0;
  }
  const step = 60/3600, tolerance = 0.1/3600;
  let left = start, visible = above(start), open = visible ? start : null;
  const intervals = [];
  while (left < end) {
    const right = Math.min(end, left + step), next = above(right);
    if (next !== visible) {
      let lo = left, hi = right;
      while (hi-lo > tolerance) {
        const mid = (lo+hi)/2;
        if (above(mid) === visible) lo = mid; else hi = mid;
      }
      const root = (lo+hi)/2;
      if (visible) {intervals.push([open,root]); open=null;} else open=root;
    }
    visible=next; left=right;
  }
  if (open !== null) intervals.push([open,end]);
  return {full_seconds:(end-start)*3600,
    visible_seconds:intervals.reduce((sum,[a,b])=>sum+(b-a)*3600,0),
    intervals:intervals.map(([a,b])=>[eventTime(elements,a,'lunar'),eventTime(elements,b,'lunar')])};
}

function lunar(context, elements) {
  context.obsvconst[4] = 0;
  context.p1=[];context.u1=[];context.u2=[];context.mid=[];context.u3=[];context.u4=[];context.p4=[];
  context.getall(elements);
  const contacts=[];
  // getall changes MID's flag to "no event" when no contact is above horizon.
  // Re-evaluate each real contact independently to preserve below-horizon MID.
  for (const name of ['p1','u1','u2','mid','u3','u4','p4']) {
    if ((name==='u1'||name==='u4') && elements[5]===3) continue;
    if ((name==='u2'||name==='u3') && elements[5]!==1) continue;
    const a=Array.from(context[name]); context.populatecircumstances(elements,a);
    contacts.push({contact:name.toUpperCase(),time_ut1:eventTime(elements,a[1],'lunar'),
      offset_hours:a[1],altitude_deg:a[4]*180/Math.PI,above_model_horizon:a[5]===0,source_visibility_flag:a[5]});
  }
  const phases={penumbral:lunarPhase(context,elements,elements[9],elements[15])};
  if (elements[5] < 3) phases.umbral=lunarPhase(context,elements,elements[10],elements[14]);
  if (elements[5] === 1) phases.total=lunarPhase(context,elements,elements[11],elements[13]);
  const visible=phases.penumbral.visible_seconds>0;
  const localType=phases.total?.visible_seconds>0?'T':phases.umbral?.visible_seconds>0?'P':visible?'N':'none';
  const midpoint=contacts.find(c=>c.contact==='MID');
  return {greatest_td:dateAt(elements[0]),delta_t_seconds:elements[2],
    local_geometry_type:{1:'T',2:'P',3:'N'}[elements[5]],local_visible_type:localType,
    visible,contacts,phases,local_maximum_ut1:midpoint.time_ut1,
    local_maximum_altitude_deg:midpoint.altitude_deg,
    maximum_above_model_horizon:midpoint.above_model_horizon,
    penumbral_magnitude:Number(elements[3]),umbral_magnitude:Number(elements[4]),
    visible_start_ut1:visible?phases.penumbral.intervals[0][0]:null,
    visible_end_ut1:visible?phases.penumbral.intervals.at(-1)[1]:null};
}

function run(request) {
  if (process.versions.node !== request.node_version) throw new Error(`Node ${request.node_version} required; found ${process.versions.node}`);
  const results=[];
  for (const source of request.sources) {
    const context=load(source.program,source.elements,source.entrypoint,request.location);
    const offset=source.kind==='lunar'?1:0, width=source.kind==='lunar'?22:28;
    const all=Array.from(context.elements).slice(offset);
    if (all.length%width) throw new Error('Unexpected NASA element-array width');
    for (let i=0;i<all.length;i+=width) {
      const elements=all.slice(i,i+width);
      const date=dateAt(elements[0]).slice(0,10);
      if (date<request.start||date>request.end) continue;
      const value=source.kind==='solar'?solar(context,elements):lunar(context,elements);
      results.push({kind:source.kind,element_source:source.entrypoint,...value});
    }
  }
  return results;
}

if (require.main===module) {
  try {process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
  catch (error) {process.stderr.write(error.stack+'\n');process.exitCode=1;}
}
module.exports={run,eventTime,lunarPhase,visibleCentralDuration};
