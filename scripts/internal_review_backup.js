/* Loaded only by the generated local reviewer, never by the public website. */
'use strict';
function csvCell(value) {
  let text=String(value??'');
  if (/^[=+@\-\t\r]/.test(text)) text="'"+text;
  return '"'+text.replaceAll('"','""')+'"';
}
function downloadReviewBackup() {
  const fields=['appearance_id','capture_date','bee_number','assigned_tag','tag_type','tag_id','status','image_count','angles','declared_tags','decoder_statuses','review_flags','reviewed_tag','review_status','review_note','domain_status'];
  const lines=[fields.map(csvCell).join(',')];
  for (const row of rows) lines.push(fields.map(f=>csvCell(REVIEW_FIELDS.includes(f)?review(row)[f]:row[f])).join(','));
  const blob=new Blob([lines.join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'});
  const url=URL.createObjectURL(blob), link=document.createElement('a');
  link.href=url;link.download=`cocoon_cam_review_backup_${new Date().toISOString().replace(/[:.]/g,'-')}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  $('save-status').textContent='Downloaded saved reviews. Any unsaved fields are not in the backup.';
}
const backupButton=document.createElement('button');
backupButton.id='download';backupButton.textContent='Download review backup CSV';
backupButton.onclick=downloadReviewBackup;
$('save-status').before(backupButton);
document.querySelector('.form-intro').textContent='Internal reviewer. Save changes in this browser, then download a backup to preserve or share proposals. Browser storage belongs to this address and is not shared with the public website.';
