'use strict';
const $ = id => document.getElementById(id);
const dataset = window.COCOON_DATA;
const rows = dataset.rows;
const STORAGE_KEY = 'cocoon-cam-2026-proposals-v1:' + location.pathname;
const REVIEW_FIELDS = ['reviewed_tag','review_status','review_note','domain_status'];
const VALID_STATUSES = ['', 'confirmed', 'corrected', 'uncertain', 'unreadable', 'duplicate', 'dorsal'];
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let edits = {};
try {
  const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  for (const row of rows) {
    const edit = stored?.[row.appearance_id];
    if (!edit || !VALID_STATUSES.includes(edit.review_status) || !['in_domain','outside_domain'].includes(edit.domain_status)) continue;
    if (!REVIEW_FIELDS.every(f => typeof edit[f] === 'string')) continue;
    edits[row.appearance_id] = Object.fromEntries(REVIEW_FIELDS.map(f => [f,edit[f]]));
  }
} catch (_) {
  $('storage-notice').hidden = false;
  $('storage-notice').textContent = 'Browser storage could not be read. The published reviews are intact. Download a backup after making changes.';
}
let filtered = [], index = 0, dirty = false;
const review = row => edits[row.appearance_id] || row;
const isDone = row => Boolean(review(row).review_status) || isOutside(row);
const isOutside = row => review(row).domain_status === 'outside_domain';
function normalizeTag(value, row) {
  const tag = String(value || '').trim().toLowerCase().replace(/\s+/g, '');
  return /^\d+$/.test(tag) && row.tag_type ? `${row.tag_type}:${tag}` : tag;
}
function reviewedTag(row) {
  const r = review(row);
  return normalizeTag(r.reviewed_tag || (r.review_status === 'confirmed' ? row.assigned_tag : ''), row);
}
function tagAuditState(row) {
  if (!isDone(row)) return 'unreviewed';
  return reviewedTag(row) && reviewedTag(row) === row.assigned_tag && !isOutside(row) ? 'match' : 'mismatch';
}
function inQueue(row, queue) {
  if (queue === 'unidentified') return !row.assigned_tag;
  if (queue === 'changed') return Boolean(row.assigned_tag && reviewedTag(row) && reviewedTag(row) !== row.assigned_tag);
  if (queue === 'disregarded') return isOutside(row);
  if (queue === 'unreviewed') return !isDone(row);
  if (queue === 'critical') return row.status !== 'assigned';
  if (queue === 'decoder') return Boolean(row.review_flags);
  if (queue === 'reuse') return Boolean(dataset.reuse[row.appearance_id]);
  return true;
}
const FILTER_HELP = {
  all: 'Includes outside-domain records. One appearance may have several images.',
  unidentified: 'No single original assignment, including missing or conflicting filename tags.',
  changed: 'An existing original tag differs from the reviewed tag. Newly identified tags are in “Initially unidentified”.',
  disregarded: 'Excluded from the published analysis unless a later review is incorporated.',
  unreviewed: 'No completed status and not outside domain. Includes unconfirmed n8tag assignments.',
  critical: 'The original metadata was missing, conflicting, or incomplete.',
  decoder: 'Original automated evidence, retained even when a manual review resolved it.',
  reuse: 'Published identities seen under multiple bee numbers on the same day; these are not recaptures.'
};
function candidates() {
  const query = $('search').value.trim().toLowerCase();
  return rows.filter(r => (!$('date').value || r.capture_date === $('date').value) && inQueue(r, $('queue').value) &&
    (!query || [r.appearance_id,r.bee_number,r.assigned_tag,r.effective_tag,r.declared_tags,reviewedTag(r)].join(' ').toLowerCase().includes(query)));
}
function current() { return filtered[index]; }
function canLeave() {
  return !dirty || confirm('This appearance has unsaved changes. Leave it without saving? Published and previously saved reviews remain intact.');
}
function updateSummary() {
  const s = dataset.summary;
  const proposals = Object.keys(edits).length;
  $('summary').textContent = `${s.appearances.toLocaleString()} appearances · ${s.images.toLocaleString()} images · ${s.capture_dates} capture dates · ${s.completed_decisions.toLocaleString()} published decisions` + (proposals ? ` · ${proposals} local proposal${proposals===1?'':'s'}` : '');
  for (const opt of $('queue').options) {
    const base = opt.dataset.label || opt.textContent;
    opt.dataset.label = base;
    opt.textContent = `${base} (${rows.filter(r => inQueue(r,opt.value)).length})`;
  }
  $('filter-help').textContent = FILTER_HELP[$('queue').value];
}
function renderList() {
  $('list').innerHTML = filtered.map((row, i) => `<button class="item audit-${tagAuditState(row)}${i===index?' selected':''}" data-index="${i}"${i===index?' aria-current="true"':''}><strong>${escapeHTML(row.appearance_id)}</strong><small>Original: ${escapeHTML(row.assigned_tag || 'unidentified')} · Review: ${escapeHTML(reviewedTag(row) || 'unresolved')}${isOutside(row)?' · outside domain':''}${edits[row.appearance_id]?' · local proposal':''}</small></button>`).join('');
  $('list').querySelectorAll('.item').forEach(item => item.onclick = () => {
    if (canLeave()) { index = Number(item.dataset.index); render(); }
  });
  $('position').textContent = filtered.length ? `${index+1} / ${filtered.length}` : '0 / 0';
  $('previous').disabled = index===0 || !filtered.length;
  $('next').disabled = index>=filtered.length-1;
  $('list').querySelector('.selected')?.scrollIntoView({block:'nearest'});
}
function renderCase() {
  const row = current();
  for (const id of ['reviewed-tag','review-status','review-note','outside-domain','save']) $(id).disabled = !row;
  $('reviewed-tag').value = row ? review(row).reviewed_tag : '';
  $('review-status').value = row ? review(row).review_status : '';
  $('review-note').value = row ? review(row).review_note : '';
  $('outside-domain').checked = row ? isOutside(row) : false;
  if (!row) {
    $('case-header').innerHTML = '<h2>No matching appearances</h2><p>Try another date, filter or search.</p>';
    $('images').replaceChildren(); $('flags').textContent=''; return;
  }
  $('case-header').innerHTML = `<h2>${escapeHTML(row.appearance_id)}</h2><div class="meta"><span class="pill">${row.images.length} image${row.images.length===1?'':'s'}</span><span class="pill">Original: ${escapeHTML(row.assigned_tag || 'unidentified')}</span><span class="pill">Published effective tag: ${escapeHTML(row.effective_tag || 'unassigned')}</span><span class="pill">${isOutside(row)?'Outside domain':escapeHTML(review(row).review_status || 'No completed decision')}</span></div>`;
  const flags = [];
  if (row.review_flags) flags.push(`Original flags: ${row.review_flags.replaceAll('_',' ').replaceAll(';', '; ')}`);
  if (row.tag_type==='n8tag' && !row.review_status) flags.push('Unconfirmed n8tag assignment remains included in published tagging totals.');
  const reuse = dataset.reuse[row.appearance_id];
  if (reuse) flags.push(`Published same-day reuse: ${reuse.tag} · bee numbers ${reuse.bee_numbers.join(', ')}.`);
  $('flags').textContent = flags.join(' | ');
  $('images').innerHTML = row.images.map((im,i) => `<figure class="image-card">${im.available?`<a href="${escapeHTML(im.url)}" target="_blank" rel="noopener"><img src="${escapeHTML(im.url)}" alt="${escapeHTML(row.appearance_id)} angle ${escapeHTML(im.angle)} image ${i+1}" decoding="async"></a>`:'<div class="image-missing">Image unavailable in this snapshot. The review record is preserved.</div>'}<figcaption>Angle ${escapeHTML(im.angle)} · image ${i+1} · filename tag: ${escapeHTML(im.declared_tag || 'unidentified')}</figcaption></figure>`).join('');
  $('images').querySelectorAll('img').forEach(im => im.addEventListener('error', () => {
    const notice=document.createElement('div');notice.className='image-missing';notice.textContent='Image failed to load. Please check your connection or reload.';im.replaceWith(notice);
  }));
}
function resetPattern() { pattern.forEach(row => row.fill(0)); }
function autofillPattern(row) {
  $('aruco-autofill').textContent = '';
  if (!row || isDone(row)) return;
  for (const im of row.images) {
    if (im.observations.length !== 1) continue;
    const o = im.observations[0];
    if (!Array.isArray(o.bits) || o.bits.length!==4 || o.bits.some(r=>!Array.isArray(r)||r.length!==4)) continue;
    o.bits.forEach((r,i)=>r.forEach((v,j)=>{pattern[i][j]=Number(Boolean(v));}));
    $('aruco-autofill').textContent=`Starting pattern from detection: ID ${o.id}, angle ${im.angle}, rotation ${o.rotation}°. Check against the image.`;
    return;
  }
  // Never seed from a filename when multiple detector candidates are present.
  if (row.images.some(im=>im.observations.length>1)) {
    $('aruco-autofill').textContent='Competing detections: enter the visible pattern manually.'; return;
  }
  const ids=[...new Set(row.images.map(im=>im.declared_tag).filter(t=>/^aruco:\d+$/.test(t)))];
  if (ids.length===1) {
    const id=Number(ids[0].split(':')[1]), bits=window.ARUCO_4X4_4000[id];
    if (bits) { bits.split('').forEach((v,i)=>{pattern[Math.floor(i/4)][i%4]=Number(v);});
      $('aruco-autofill').textContent=`Starting pattern from filename ID ${id}; rotation assumed 0°. This is not a verification.`; }
  }
}
function render() {
  filtered=candidates(); index=Math.min(index,Math.max(0,filtered.length-1));
  resetPattern(); autofillPattern(current()); renderPattern(); renderList(); renderCase(); updateSummary(); dirty=false;
}
function save() {
  const row=current(); if (!row) return;
  const edit={reviewed_tag:normalizeTag($('reviewed-tag').value,row),review_status:$('review-status').value,
    review_note:$('review-note').value.trim(),domain_status:$('outside-domain').checked?'outside_domain':'in_domain'};
  if (edit.reviewed_tag && !/^(aruco|n8tag):\d+$/.test(edit.reviewed_tag)) {
    $('save-status').textContent='Use a tag such as aruco:123 or n8tag:12.';return;
  }
  if (edit.review_status==='corrected' && !edit.reviewed_tag) {
    $('save-status').textContent='Enter a tag for a corrected review.';return;
  }
  const proposed={...edits,[row.appearance_id]:edit};
  try { localStorage.setItem(STORAGE_KEY,JSON.stringify(proposed)); }
  catch (_) { edits=proposed;dirty=false;updateSummary();$('save-status').textContent='Browser storage failed. Change is in memory only—download a backup now.';return; }
  edits=proposed;dirty=false;
  const oldIndex=index, nextId=filtered[index+1]?.appearance_id;
  filtered=candidates();
  const nextIndex=filtered.findIndex(r=>r.appearance_id===nextId);
  index=nextIndex>=0?nextIndex:Math.min(oldIndex,Math.max(0,filtered.length-1));
  render();$('save-status').textContent=`Saved ${row.appearance_id} in this browser. Download to share.`;
}
function csvCell(value) {
  let text=String(value??'');
  if (/^[=+@\-\t\r]/.test(text)) text="'"+text;
  return '"'+text.replaceAll('"','""')+'"';
}
function download() {
  const fields=['appearance_id','capture_date','bee_number','assigned_tag','tag_type','tag_id','status','image_count','angles','declared_tags','decoder_statuses','review_flags','reviewed_tag','review_status','review_note','domain_status'];
  const lines=[fields.map(csvCell).join(',')];
  for (const row of rows) lines.push(fields.map(f=>csvCell(REVIEW_FIELDS.includes(f)?review(row)[f]:row[f])).join(','));
  const blob=new Blob([lines.join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'});
  const url=URL.createObjectURL(blob), link=document.createElement('a');
  link.href=url;link.download=`cocoon_cam_review_backup_${new Date().toISOString().replace(/[:.]/g,'-')}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  $('save-status').textContent='Downloaded saved reviews. Any unsaved fields are not in the backup.';
}
for (const day of [...new Set(rows.map(r=>r.capture_date))].sort()) {
  const opt=document.createElement('option');opt.value=day;opt.textContent=`${day} (${rows.filter(r=>r.capture_date===day).length})`;$('date').append(opt);
}
for (const id of ['date','queue']) {
  $(id).dataset.previous=$(id).value;
  $(id).onchange=()=> { if (!canLeave()) {$(id).value=$(id).dataset.previous;return;} $(id).dataset.previous=$(id).value;index=0;render(); };
}
$('search').oninput=()=> {if (dirty) { $('save-status').textContent='Save the current changes before searching.';return;}index=0;render();};
$('previous').onclick=()=>{if (canLeave()&&index>0){index--;render();}};
$('next').onclick=()=>{if(canLeave()&&index<filtered.length-1){index++;render();}};
$('save').onclick=save; $('download').onclick=download;
for (const id of ['reviewed-tag','review-status','review-note','outside-domain']) $(id).addEventListener('input',()=>{dirty=true;});
$('review-status').addEventListener('change',()=> {if ($('review-status').value==='dorsal') $('reviewed-tag').value='';});
function switchTab(name) {
  for (const tab of ['review','timeline']) {
    const selected=tab===name;$('tab-'+tab).setAttribute('aria-selected',String(selected));$('tab-'+tab).tabIndex=selected?0:-1;$(tab+'-panel').hidden=!selected;
  }
}
for (const name of ['review','timeline']) {
  $('tab-'+name).onclick=()=>switchTab(name);
  $('tab-'+name).onkeydown=e=> {if (['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) {e.preventDefault();const next=e.key==='Home'?'review':e.key==='End'?'timeline':name==='review'?'timeline':'review';switchTab(next);$('tab-'+next).focus();}};
}
const s=dataset.summary;
$('metrics').innerHTML=[[s.unique_identities,'Unique tag identities'],[s.aruco_recapture_events,'Later-date ArUco recaptures'],[s.capture_dates,'Recorded capture dates'],[s.outside_domain,'Outside-domain appearances']].map(([n,label])=>`<div class="metric"><strong>${n.toLocaleString()}</strong><span>${label}</span></div>`).join('');
$('recapture-average').textContent=s.mean_recapture_days == null ? 'No recaptures' : `${s.mean_recapture_days.toFixed(1)} days`;
$('recapture-average-detail').textContent=s.mean_recapture_days == null ? 'No later-date ArUco captures in this snapshot.' : `First recorded capture to each recapture · ${s.aruco_recapture_events} events across ${s.recaptured_aruco_tags} ArUco tags · Range: ${s.min_recapture_days}–${s.max_recapture_days} days`;
const columns=[['capture_date','Date'],['new_bees_tagged','New tags'],['aruco_captures','ArUco captures'],['n8tag_captures','n8tag captures'],['recaptured_aruco_individuals','ArUco recaptures'],['cumulative_unique_bees','Cumulative identities'],['cumulative_aruco_recaptures','Cumulative recaptures']];
$('daily-table').innerHTML='<thead><tr>'+columns.map(c=>`<th scope="col">${c[1]}</th>`).join('')+'</tr></thead><tbody>'+dataset.daily.map(r=>'<tr>'+columns.map(c=>`<td>${escapeHTML(r[c[0]])}</td>`).join('')+'</tr>').join('')+'</tbody>';
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
const pattern = Array.from({ length: 4 }, () => Array(4).fill(0));
function rotatePattern(source) { return source[0].map((_, col) => source.map(row => row[col]).reverse()); }
function patternBits(source) { return source.flat().join(''); }
function decodePattern() {
  let candidate = pattern.map(row => row.slice());
  const matches = [];
  for (let rotation = 0; rotation < 4; rotation += 1) {
    const bits = patternBits(candidate);
    ARUCO_4X4_4000.forEach((dictionaryBits, id) => { if (dictionaryBits === bits) matches.push({ id, rotation: rotation * 90 }); });
    candidate = rotatePattern(candidate);
  }
  const unique = [...new Map(matches.map(match => [match.id, match])).values()];
  $('aruco-result').textContent = unique.length ? unique.map(match => `ID ${match.id} (${match.rotation}°)`).join(', ') : 'No exact dictionary match';
  $('aruco-use').disabled = unique.length !== 1;
  $('aruco-use').dataset.id = unique.length === 1 ? unique[0].id : '';
}
function renderPattern() {
  const cells = [];
  for (let row = 0; row < 6; row += 1) for (let col = 0; col < 6; col += 1) {
    if (row === 0 || row === 5 || col === 0 || col === 5) cells.push('<div class="aruco-cell" aria-hidden="true"></div>');
    else { const white = pattern[row - 1][col - 1] ? ' white' : ''; cells.push(`<button class="aruco-cell editable${white}" data-row="${row - 1}" data-col="${col - 1}" aria-label="Pattern row ${row}, column ${col}"></button>`); }
  }
  $('aruco-grid').innerHTML = cells.join('');
  document.querySelectorAll('.aruco-cell.editable').forEach(cell => cell.onclick = () => { const row = Number(cell.dataset.row); const col = Number(cell.dataset.col); pattern[row][col] = pattern[row][col] ? 0 : 1; cell.classList.toggle('white', Boolean(pattern[row][col])); decodePattern(); });
  decodePattern();
}
$('aruco-reset').onclick=()=>{resetPattern();renderPattern();};
$('aruco-use').onclick=()=>{const id=$('aruco-use').dataset.id;if(id&&current()){$('reviewed-tag').value=`aruco:${id}`;$('review-status').value='confirmed';dirty=true;}};
document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT','BUTTON'].includes(document.activeElement.tagName)||$('review-panel').hidden)return;if(e.key==='ArrowLeft')$('previous').click();if(e.key==='ArrowRight')$('next').click();if(e.key.toLowerCase()==='s')save();});
render();
