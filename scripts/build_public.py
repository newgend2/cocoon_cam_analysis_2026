"""Build an allowlisted public dataset from an archived reviewed snapshot."""
import argparse
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

APPEARANCE_FIELDS = ['appearance_id', 'capture_date', 'bee_number', 'assigned_tag',
    'tag_type', 'tag_id', 'status', 'image_count', 'angles', 'declared_tags',
    'decoder_statuses', 'review_flags', 'source_assigned_tag', 'source_status',
    'reviewed_tag', 'review_status', 'review_note', 'domain_status', 'analysis_included']
IMAGE_FIELDS = ['capture_date', 'bee_number', 'angle_number', 'tag_type', 'tag_id',
    'declared_key', 'image_status', 'observed_ids', 'appearance_id', 'reviewed_tag',
    'review_status', 'review_note', 'domain_status', 'analysis_included']
BEE_FIELDS = ['bee_id', 'tag_type', 'tag_id', 'first_appearance', 'last_appearance',
    'appearance_count', 'appearance_dates', 'timeline', 'image_count', 'verification',
    'review_statuses', 'review_flags']
REVIEW_FIELDS = ['appearance_id', 'capture_date', 'bee_number', 'assigned_tag',
    'tag_type', 'tag_id', 'status', 'image_count', 'angles', 'declared_tags',
    'decoder_statuses', 'review_flags', 'reviewed_tag', 'review_status', 'review_note', 'domain_status']


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def load_js(path):
    return json.loads(path.read_text().split('=', 1)[1].strip().rstrip(';'))


def timeline(rows):
    by_date = defaultdict(set)
    for row in rows:
        by_date[row['capture_date']]
        if row['analysis_included'] == 'true' and row['assigned_tag']:
            by_date[row['capture_date']].add(row['assigned_tag'])
    seen = set()
    daily = []
    for day, tags in sorted(by_date.items()):
        aruco = {t for t in tags if t.startswith('aruco:')}
        n8 = tags - aruco
        fresh = tags - seen
        daily.append(dict(capture_date=day, unique_tagged_appearance_count=len(tags),
            aruco_captures=len(aruco), n8tag_captures=len(n8), new_bees_tagged=len(fresh),
            new_aruco_tags=len(aruco-seen), new_n8tags=len(n8-seen),
            recaptured_aruco_individuals=len(aruco & seen), cumulative_unique_bees=len(seen | tags)))
        seen |= tags
    return daily


def plot_timeline(daily, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    days = [date.fromisoformat(r['capture_date']) for r in daily]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'svg.hashsalt': 'cocoon-cam-2026'})
    fig, axes = plt.subplots(3, 1, figsize=(16, 8), sharex=True,
                             gridspec_kw={'height_ratios': [1, 1, 1.2]})
    fig.suptitle('Cocoon cam · Emerald Queen 2026', x=.065, ha='left', fontsize=19, fontweight='bold')
    axes[0].bar(days, [r['new_bees_tagged'] for r in daily], width=.72, color='#246c59')
    axes[1].bar(days, [r['recaptured_aruco_individuals'] for r in daily], width=.72, color='#b17d22')
    axes[2].step(days, [r['cumulative_unique_bees'] for r in daily], where='post', color='#345e95', lw=2)
    axes[2].scatter(days, [r['cumulative_unique_bees'] for r in daily], color='#345e95', s=15)
    titles = ['New tag identities (ArUco + n8tag)', 'Later-date ArUco recapture events', 'Cumulative unique tag identities']
    cursor = days[0]
    while cursor <= days[-1]:
        if cursor not in days:
            for ax in axes:
                ax.axvspan(mdates.date2num(cursor)-.5, mdates.date2num(cursor)+.5, color='#f0f0ed', zorder=0)
        cursor += timedelta(days=1)
    for ax, title in zip(axes, titles):
        ax.set_title(title, loc='left', fontsize=12, pad=9)
        ax.set_ylabel('Tag identities' if ax is axes[2] else 'Count')
        ax.set_ylim(bottom=0)
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', alpha=.2)
    for ax, field in [(axes[0], 'new_bees_tagged'), (axes[1], 'recaptured_aruco_individuals')]:
        ax.set_ylim(0,max(r[field] for r in daily)*1.22)
        for i, (d, r) in enumerate(zip(days, daily)):
            if r[field]:
                offset=11 if i and (d-days[i-1]).days==1 and abs(r[field]-daily[i-1][field])<=10 else 4
                ax.annotate(str(r[field]), (mdates.date2num(d), r[field]), xytext=(0, offset), textcoords='offset points', ha='center', fontsize=8)
    axes[-1].xaxis.set_major_locator(mdates.DayLocator(interval=1))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%d'))
    axes[-1].set_xlim(mdates.date2num(days[0])-.6, mdates.date2num(days[-1])+.6)
    plt.setp(axes[-1].get_xticklabels(), rotation=90, ha='center', fontsize=9)
    # Each day retains its full date as a stable SVG identifier; visible day
    # numbers are grouped by month to stay readable when the figure fits a page.
    for tick, location in zip(axes[-1].get_xticklabels(), axes[-1].get_xticks()):
        tick.set_gid('date-'+mdates.num2date(location).strftime('%Y-%m-%d'))
    month_start=days[0].replace(day=1)
    while month_start <= days[-1]:
        next_month=(month_start.replace(day=28)+timedelta(days=4)).replace(day=1)
        lo=max(month_start,days[0]);hi=min(next_month-timedelta(days=1),days[-1])
        left=mdates.date2num(lo)-.45;right=mdates.date2num(hi)+.45
        axes[-1].plot([left,right],[-.24,-.24],transform=axes[-1].get_xaxis_transform(),clip_on=False,color='#79847d',lw=.8)
        axes[-1].text((left+right)/2,-.30,month_start.strftime('%B %Y'),
                      transform=axes[-1].get_xaxis_transform(),ha='center',va='top',fontsize=10,fontweight='bold')
        if month_start>days[0]:
            for ax in axes:ax.axvline(mdates.date2num(month_start)-.5,color='#b4bcb6',lw=.8)
        month_start=next_month
    fig.text(.065,.035,'Gray bands: no capture records (not zero observed captures). Same tag + same day counts once. ArUco recaptures require a later date.\n'
             'Outside-domain and unassigned records excluded; unconfirmed n8tags remain included. Browser proposals do not change this snapshot.',fontsize=8.5)
    fig.subplots_adjust(left=.065, right=.987, top=.90, bottom=.22, hspace=.53)
    fig.savefig(output/'tagging_and_recapture_graphs.svg', metadata={'Date': None, 'Creator': 'Cocoon cam analysis'})
    svg_path = output/'tagging_and_recapture_graphs.svg'
    svg_text = svg_path.read_text().replace("font-family: 'DejaVu Sans'", "font-family: 'DejaVu Sans', Arial, sans-serif")
    svg_path.write_text('\n'.join(line.rstrip() for line in svg_text.splitlines())+'\n')
    fig.savefig(output/'tagging_and_recapture_graphs.png', dpi=150, metadata={'Software': 'Cocoon cam analysis'})
    plt.close(fig)


def build(source, output):
    downloads = output/'downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    appearances = read_csv(source/'records/appearance_records_reviewed.csv')
    images = read_csv(source/'records/image_records_reviewed.csv')
    reviews = read_csv(source/'records/manual_review_input.csv')
    bees = read_csv(source/'records/bee_records_reviewed.csv')
    observations = load_js(source/'viewer/aruco_observations.js')
    images_by_appearance = defaultdict(list)
    public_images = []
    for im in images:
        image_id = im['sha256'][:20]
        image_url = f'images/{image_id}.webp'
        entry = dict(image_id=image_id, angle=im['angle_number'], url=image_url,
                     available=(output/image_url).exists(), declared_tag=im['declared_key'],
                     observations=observations.get(im['path'], []))
        # Explicit observation schema avoids retaining implementation/source metadata.
        entry['observations'] = [{k: o[k] for k in ['id','rotation','bits'] if k in o} for o in entry['observations']]
        images_by_appearance[im['appearance_id']].append(entry)
        public_images.append({**{f: im[f] for f in IMAGE_FIELDS}, 'image_id': image_id,
                              'image_file': image_id+'.webp', 'image_available': str(entry['available']).lower()})
    review_by_id = {r['appearance_id']: r for r in reviews}
    rows = []
    for a in appearances:
        row = {f: a[f] for f in APPEARANCE_FIELDS}
        row['effective_tag'] = a['assigned_tag']
        for field in ['assigned_tag', 'tag_type', 'tag_id', 'status']:
            row[field] = review_by_id[a['appearance_id']][field]
        row['images'] = images_by_appearance[a['appearance_id']]
        rows.append(row)
    daily = timeline(appearances)
    previous = read_csv(source/'graphs/tagging_recapture_by_date.csv')
    assert [{k: str(v) for k,v in r.items()} for r in daily] == previous, 'Timeline changed from archived source'
    write_csv(downloads/'appearance_records_reviewed.csv', appearances, APPEARANCE_FIELDS)
    write_csv(downloads/'image_records_reviewed.csv', public_images, ['image_id','image_file','image_available']+IMAGE_FIELDS)
    write_csv(downloads/'bee_records_reviewed.csv', bees, BEE_FIELDS)
    write_csv(downloads/'published_reviews.csv', reviews, REVIEW_FIELDS)
    write_csv(downloads/'tagging_recapture_by_date.csv', daily, list(daily[0]))
    calendar = []
    lookup = {r['capture_date']: r for r in daily}
    cursor = date.fromisoformat(daily[0]['capture_date'])
    end = date.fromisoformat(daily[-1]['capture_date'])
    cumulative = 0
    while cursor <= end:
        ds = str(cursor)
        r = lookup.get(ds)
        if r: cumulative = r['cumulative_unique_bees']
        calendar.append({'capture_date': ds, 'capture_records_present': str(bool(r)).lower(),
                         **{f: r[f] if r else (cumulative if f=='cumulative_unique_bees' else '') for f in daily[0] if f!='capture_date'}})
        cursor += timedelta(days=1)
    write_csv(downloads/'calendar_timeline.csv', calendar, list(calendar[0]))
    groups = defaultdict(list)
    for a in appearances:
        if a['analysis_included']=='true' and a['assigned_tag']:
            groups[(a['capture_date'], a['assigned_tag'])].append(a)
    reuse = {a['appearance_id']: {'tag': tag, 'date': day, 'bee_numbers': [x['bee_number'] for x in group]}
             for (day,tag),group in groups.items() if len(group)>1 for a in group}
    summary = dict(appearances=len(rows), images=len(images), capture_dates=len(daily),
        completed_decisions=sum(bool(r['review_status']) or r['domain_status']=='outside_domain' for r in rows),
        unique_identities=len(bees), aruco_identities=sum(b['tag_type']=='aruco' for b in bees),
        n8tag_identities=sum(b['tag_type']=='n8tag' for b in bees),
        aruco_recapture_events=sum(r['recaptured_aruco_individuals'] for r in daily),
        outside_domain=sum(r['domain_status']=='outside_domain' for r in rows),
        unassigned_in_domain=sum(r['analysis_included']=='true' and not r['effective_tag'] for r in rows),
        unconfirmed_n8tag=sum(r['tag_type']=='n8tag' and not r['review_status'] and r['analysis_included']=='true' for r in rows),
        images_available=sum(im['image_available']=='true' for im in public_images),
        snapshot='2026-09-16', source_review_sha256=hashlib.sha256((source/'records/manual_review_input.csv').read_bytes()).hexdigest())
    payload = {'rows': rows, 'daily': daily, 'summary': summary, 'reuse': reuse}
    (output/'data.js').write_text('window.COCOON_DATA = '+json.dumps(payload,separators=(',',':')).replace('<','\\u003c')+';\n')
    shutil.copyfile(source/'viewer/aruco_dict.js', output/'aruco_dict.js')
    (downloads/'dataset_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    plot_timeline(daily, downloads)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('docs'))
    args=parser.parse_args()
    build(args.source,args.output)
