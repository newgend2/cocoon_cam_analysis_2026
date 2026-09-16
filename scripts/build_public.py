"""Build an allowlisted public dataset from an archived reviewed snapshot."""
import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
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
INTERVAL_FIELDS = ['assigned_tag', 'first_capture_date', 'recapture_date',
    'recapture_number', 'days_since_first_capture']
INTERNAL_EXPORT_NAMES = [
    'appearance_records_reviewed.csv', 'image_records_reviewed.csv',
    'bee_records_reviewed.csv', 'published_reviews.csv',
    'tagging_recapture_by_date.csv', 'calendar_timeline.csv',
    'recapture_intervals.csv', 'recapture_interval_counts.csv',
    'dataset_summary.json', 'README.txt']


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
    cumulative_recaptures = 0
    for day, tags in sorted(by_date.items()):
        aruco = {t for t in tags if t.startswith('aruco:')}
        n8 = tags - aruco
        fresh = tags - seen
        cumulative_recaptures += len(aruco & seen)
        daily.append(dict(capture_date=day, unique_tagged_appearance_count=len(tags),
            aruco_captures=len(aruco), n8tag_captures=len(n8), new_bees_tagged=len(fresh),
            new_aruco_tags=len(aruco-seen), new_n8tags=len(n8-seen),
            recaptured_aruco_individuals=len(aruco & seen), cumulative_unique_bees=len(seen | tags),
            cumulative_aruco_recaptures=cumulative_recaptures))
        seen |= tags
    return daily


def recapture_intervals(rows):
    """One interval per later ArUco tag/date, measured from its first appearance."""
    dates_by_tag = defaultdict(set)
    for row in rows:
        tag = row['assigned_tag']
        if row['analysis_included'] == 'true' and tag.startswith('aruco:'):
            dates_by_tag[tag].add(date.fromisoformat(row['capture_date']))
    intervals = []
    for tag, dates in sorted(dates_by_tag.items()):
        ordered = sorted(dates)
        for number, day in enumerate(ordered[1:], start=1):
            intervals.append(dict(assigned_tag=tag, first_capture_date=str(ordered[0]),
                recapture_date=str(day), recapture_number=number,
                days_since_first_capture=(day-ordered[0]).days))
    return sorted(intervals, key=lambda r: (r['recapture_date'], r['assigned_tag']))


def recapture_summary(intervals):
    values = [r['days_since_first_capture'] for r in intervals]
    return dict(recaptured_aruco_tags=len({r['assigned_tag'] for r in intervals}),
        mean_recapture_days=sum(values)/len(values) if values else None,
        min_recapture_days=min(values) if values else None,
        max_recapture_days=max(values) if values else None)


def master_capture_history(rows):
    """One row per included tag, with ordered later-date ArUco recaptures."""
    dates_by_tag = defaultdict(set)
    bee_numbers_by_tag_date = defaultdict(set)
    for row in rows:
        if row['analysis_included'] == 'true' and row['assigned_tag']:
            dates_by_tag[row['assigned_tag']].add(row['capture_date'])
            bee_numbers_by_tag_date[(row['assigned_tag'], row['capture_date'])].add(row['bee_number'])
    intervals_by_tag = defaultdict(list)
    for interval in recapture_intervals(rows):
        intervals_by_tag[interval['assigned_tag']].append(interval['recapture_date'])
    max_recaptures = max((len(days) for days in intervals_by_tag.values()), default=0)
    fields = ['tag_id', 'bee_number', 'first_assignment_date', 'recaptured'] + [
        f'recapture_{i}_date' for i in range(1, max(1, max_recaptures)+1)]
    result = []
    for tag in sorted(dates_by_tag, key=lambda t: (t.split(':')[0], int(t.split(':')[1]))):
        recaptures = sorted(intervals_by_tag[tag])
        first_date = min(dates_by_tag[tag])
        bee_numbers = sorted(bee_numbers_by_tag_date[(tag, first_date)], key=int)
        result.append(dict(tag_id=tag, bee_number=';'.join(bee_numbers), first_assignment_date=first_date,
            recaptured=str(bool(recaptures)).lower(),
            **{f'recapture_{i}_date': day for i, day in enumerate(recaptures, start=1)}))
    return result, fields


def build_internal_viewer(output, internal):
    """Keep review backup available locally, outside the published directory."""
    viewer = internal/'viewer'
    viewer.mkdir(exist_ok=True)
    for name in ['index.html', 'style.css', 'app.js', 'data.js', 'aruco_dict.js']:
        shutil.copyfile(output/name, viewer/name)
    page = viewer/'index.html'
    page.write_text(page.read_text().replace('</body>', '<script src="review_backup.js"></script>\n</body>'))
    shutil.copyfile(Path(__file__).with_name('internal_review_backup.js'), viewer/'review_backup.js')
    for name in ['images', 'downloads']:
        link = viewer/name
        target = (output/'images' if name == 'images' else internal).resolve()
        if link.is_symlink():
            if link.resolve() == target:
                continue
            link.unlink()
        link.symlink_to(target, target_is_directory=True)


def plot_timeline(daily, intervals, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    days = [date.fromisoformat(r['capture_date']) for r in daily]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'svg.hashsalt': 'cocoon-cam-2026'})
    from matplotlib.ticker import MaxNLocator
    fig, axes = plt.subplots(3, 1, figsize=(16, 10),
                             gridspec_kw={'height_ratios': [1, 1, 1.1]})
    axes[1].sharex(axes[0])
    timeline_axes = axes[:2]
    fig.suptitle('Cocoon cam · Emerald Queen 2026', x=.065, ha='left', fontsize=19, fontweight='bold')
    panels = [
        ('new_bees_tagged', 'cumulative_unique_bees', '#246c59', 'New IDs', "cumulative ID's",
         'New tag identities (ArUco + n8tag)', 'Cumulative IDs'),
        ('recaptured_aruco_individuals', 'cumulative_aruco_recaptures', '#b17d22', 'Daily recaptures',
         'cumulative recaptures', 'Later-date ArUco recapture events', 'Cumulative recaptures')]
    for ax, (field, cumulative, color, bar_label, line_label, title, right_label) in zip(timeline_axes, panels):
        bars = ax.bar(days, [r[field] for r in daily], width=.72, color=color, label=bar_label)
        total_ax = ax.twinx()
        line, = total_ax.step(days, [r[cumulative] for r in daily], where='post', color='#345e95',
                              lw=2, label=line_label)
        total_ax.set_ylabel(right_label, color='#345e95')
        total_ax.tick_params(axis='y', colors='#345e95')
        total_ax.set_ylim(0, max(1, daily[-1][cumulative])*1.25)
        total_ax.spines[['top', 'left']].set_visible(False)
        total_ax.spines['right'].set_color('#345e95')
        total_ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
        ax.set_title(title, loc='left', fontsize=12, pad=10)
        ax.set_ylabel('Daily count')
        ax.set_ylim(0, max(1, max(r[field] for r in daily))*1.35)
        total_ax.legend(handles=[bars, line], loc='upper left', frameon=True, framealpha=.95,
                        edgecolor='none', fontsize=10, ncol=2)
        for i, (d, r) in enumerate(zip(days, daily)):
            if r[field]:
                offset=11 if i and (d-days[i-1]).days==1 and abs(r[field]-daily[i-1][field])<=10 else 4
                total_ax.annotate(str(r[field]), (mdates.date2num(d), r[field]), xycoords=ax.transData,
                                  xytext=(0, offset), textcoords='offset points', ha='center', fontsize=8,
                                  bbox=dict(facecolor='white', edgecolor='none', pad=.5), zorder=5)
    cursor = days[0]
    while cursor <= days[-1]:
        if cursor not in days:
            for ax in timeline_axes:
                ax.axvspan(mdates.date2num(cursor)-.5, mdates.date2num(cursor)+.5, color='#f0f0ed', zorder=0)
        cursor += timedelta(days=1)
    for ax in axes:
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    date_axis = axes[1]
    axes[0].tick_params(axis='x', labelbottom=False)
    date_axis.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    date_axis.xaxis.set_major_formatter(mdates.DateFormatter('%d'))
    date_axis.set_xlim(mdates.date2num(days[0])-.6, mdates.date2num(days[-1])+.6)
    plt.setp(date_axis.get_xticklabels(), rotation=90, ha='center', fontsize=9)
    # Each day retains its full date as a stable SVG identifier; visible day
    # numbers are grouped by month to stay readable when the figure fits a page.
    for tick, location in zip(date_axis.get_xticklabels(), date_axis.get_xticks()):
        tick.set_gid('date-'+mdates.num2date(location).strftime('%Y-%m-%d'))
    month_start=days[0].replace(day=1)
    while month_start <= days[-1]:
        next_month=(month_start.replace(day=28)+timedelta(days=4)).replace(day=1)
        lo=max(month_start,days[0]);hi=min(next_month-timedelta(days=1),days[-1])
        left=mdates.date2num(lo)-.45;right=mdates.date2num(hi)+.45
        date_axis.plot([left,right],[-.24,-.24],transform=date_axis.get_xaxis_transform(),clip_on=False,color='#79847d',lw=.8)
        date_axis.text((left+right)/2,-.30,month_start.strftime('%B %Y'),
                      transform=date_axis.get_xaxis_transform(),ha='center',va='top',fontsize=10,fontweight='bold')
        if month_start>days[0]:
            for ax in timeline_axes:ax.axvline(mdates.date2num(month_start)-.5,color='#b4bcb6',lw=.8)
        month_start=next_month
    counts = Counter(r['days_since_first_capture'] for r in intervals)
    interval_ax = axes[2]
    interval_ax.set_title('Time from first recorded capture to each recapture', loc='left', fontsize=12, pad=10)
    interval_ax.set_xlabel('Days since first recorded capture')
    interval_ax.set_ylabel('Recapture events')
    interval_ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    if intervals:
        values = list(range(1, max(counts)+1))
        interval_ax.bar(values, [counts[v] for v in values], width=.75, color='#78679c')
        stats = recapture_summary(intervals)
        mean = stats['mean_recapture_days']
        interval_ax.axvline(mean, color='#345e95', ls='--', lw=2, label=f'Overall average: {mean:.1f} days')
        interval_ax.legend(loc='upper right', frameon=False, fontsize=11)
        interval_ax.text(.99, .74, f"{len(intervals)} recapture events · {stats['recaptured_aruco_tags']} ArUco tags",
                         transform=interval_ax.transAxes, ha='right', fontsize=10)
        interval_ax.set_xticks(values)
        interval_ax.tick_params(axis='x', labelsize=8)
        interval_ax.set_xlim(.25, max(counts)+.75)
        interval_ax.set_ylim(0, max(counts.values())*1.20)
        for value, count in sorted(counts.items()):
            interval_ax.annotate(str(count), (value, count), xytext=(0, 4), textcoords='offset points', ha='center', fontsize=8)
    else:
        interval_ax.text(.5, .5, 'No later-date ArUco recaptures', transform=interval_ax.transAxes, ha='center')
    fig.text(.065,.054,'Intervals use the first recorded appearance as the initial tagging date; each later tag/date contributes one interval.\n'
             'The mean weights recapture events equally, so tags seen on several later dates contribute several intervals.', fontsize=8.5)
    fig.text(.065,.014,'Gray bands: no capture records (not zero observed captures). Same tag + same day counts once. ArUco recaptures require a later date.\n'
             'Outside-domain and unassigned records excluded; unconfirmed n8tags remain included. Browser proposals do not change this snapshot.',fontsize=8.5)
    fig.subplots_adjust(left=.065, right=.93, top=.90, bottom=.14, hspace=.78)
    fig.savefig(output/'tagging_and_recapture_graphs.svg', metadata={'Date': None, 'Creator': 'Cocoon cam analysis'})
    svg_path = output/'tagging_and_recapture_graphs.svg'
    svg_text = svg_path.read_text().replace("font-family: 'DejaVu Sans'", "font-family: 'DejaVu Sans', Arial, sans-serif")
    svg_path.write_text('\n'.join(line.rstrip() for line in svg_text.splitlines())+'\n')
    fig.savefig(output/'tagging_and_recapture_graphs.png', dpi=150, metadata={'Software': 'Cocoon cam analysis'})
    plt.close(fig)


def build(source, output, internal):
    if internal.resolve().is_relative_to(output.resolve()) or output.resolve().is_relative_to(internal.resolve()):
        raise ValueError('Internal exports and the public site must use separate directories')
    downloads = output/'downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    internal.mkdir(parents=True, exist_ok=True)
    # Preserve exact copies before retiring the old public download endpoints.
    for name in INTERNAL_EXPORT_NAMES:
        old = downloads/name
        if old.exists():
            archive = internal/'retired_public_exports'
            archive.mkdir(exist_ok=True)
            preserved = archive/name
            if preserved.exists() and preserved.read_bytes() != old.read_bytes():
                raise ValueError(f'Existing retired export differs: {name}')
            shutil.copyfile(old, preserved)
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
    assert [{k: str(r[k]) for k in previous[0]} for r in daily] == previous, 'Timeline changed from archived source'
    intervals = recapture_intervals(appearances)
    assert Counter(r['recapture_date'] for r in intervals) == Counter({
        r['capture_date']: r['recaptured_aruco_individuals'] for r in daily}), 'Recapture interval counts disagree with timeline'
    write_csv(internal/'appearance_records_reviewed.csv', appearances, APPEARANCE_FIELDS)
    write_csv(internal/'image_records_reviewed.csv', public_images, ['image_id','image_file','image_available']+IMAGE_FIELDS)
    write_csv(internal/'bee_records_reviewed.csv', bees, BEE_FIELDS)
    write_csv(internal/'published_reviews.csv', reviews, REVIEW_FIELDS)
    write_csv(internal/'tagging_recapture_by_date.csv', daily, list(daily[0]))
    write_csv(internal/'recapture_intervals.csv', intervals, INTERVAL_FIELDS)
    master, master_fields = master_capture_history(appearances)
    write_csv(downloads/'master_capture_history.csv', master, master_fields)
    shutil.copyfile(downloads/'master_capture_history.csv', internal/'master_capture_history.csv')
    distribution = Counter(r['days_since_first_capture'] for r in intervals)
    write_csv(internal/'recapture_interval_counts.csv', [
        dict(days_since_first_capture=d, recapture_events=distribution[d])
        for d in range(1, max(distribution, default=0)+1)], ['days_since_first_capture', 'recapture_events'])
    calendar = []
    lookup = {r['capture_date']: r for r in daily}
    cursor = date.fromisoformat(daily[0]['capture_date'])
    end = date.fromisoformat(daily[-1]['capture_date'])
    cumulative = {'cumulative_unique_bees': 0, 'cumulative_aruco_recaptures': 0}
    while cursor <= end:
        ds = str(cursor)
        r = lookup.get(ds)
        if r: cumulative = {f: r[f] for f in cumulative}
        calendar.append({'capture_date': ds, 'capture_records_present': str(bool(r)).lower(),
                         **{f: r[f] if r else cumulative.get(f, '') for f in daily[0] if f!='capture_date'}})
        cursor += timedelta(days=1)
    write_csv(internal/'calendar_timeline.csv', calendar, list(calendar[0]))
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
        **recapture_summary(intervals),
        snapshot='2026-09-16', source_review_sha256=hashlib.sha256((source/'records/manual_review_input.csv').read_bytes()).hexdigest())
    payload = {'rows': rows, 'daily': daily, 'summary': summary, 'reuse': reuse}
    (output/'data.js').write_text('window.COCOON_DATA = '+json.dumps(payload,separators=(',',':')).replace('<','\\u003c')+';\n')
    shutil.copyfile(source/'viewer/aruco_dict.js', output/'aruco_dict.js')
    (internal/'dataset_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    internal_readme = internal/'retired_public_exports/README.txt'
    if internal_readme.exists():
        shutil.copyfile(internal_readme, internal/'README.txt')
    plot_timeline(daily, intervals, downloads)
    for name in ['tagging_and_recapture_graphs.svg', 'tagging_and_recapture_graphs.png']:
        shutil.copyfile(downloads/name, internal/name)
    build_internal_viewer(output, internal)
    for name in INTERNAL_EXPORT_NAMES:
        (downloads/name).unlink(missing_ok=True)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('docs'))
    parser.add_argument('--internal-output',type=Path,default=Path('private/analysis_exports'))
    args=parser.parse_args()
    build(args.source,args.output,args.internal_output)
