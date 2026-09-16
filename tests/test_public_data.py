import csv
import json
import sys
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_public import timeline, recapture_intervals, recapture_summary


def table(name):
    with (ROOT/'docs/downloads'/name).open(newline='') as f:return list(csv.DictReader(f))


class CaptureRules(unittest.TestCase):
    def test_recaptures_are_later_date_aruco_only(self):
        rows=[dict(capture_date=d,assigned_tag=t,analysis_included=i) for d,t,i in [
            ('2026-01-01','aruco:1','true'),('2026-01-01','aruco:1','true'),
            ('2026-01-01','n8tag:1','true'),('2026-01-02','aruco:1','true'),
            ('2026-01-02','n8tag:1','true'),('2026-01-02','aruco:2','false'),
            ('2026-01-03','','true'),('2026-01-03','aruco:3','false')]]
        result=timeline(rows)
        self.assertEqual([r['new_bees_tagged'] for r in result],[2,0,0])
        self.assertEqual([r['recaptured_aruco_individuals'] for r in result],[0,1,0])
        self.assertEqual([r['cumulative_unique_bees'] for r in result],[2,2,2])
        self.assertEqual([r['cumulative_aruco_recaptures'] for r in result],[0,1,1])

    def test_intervals_use_first_capture_and_count_each_later_date_once(self):
        # Unsorted input, duplicate same-day images/appearances, an excluded
        # earlier claim, separate namespaces and a tag never recaptured.
        rows=[dict(capture_date=d,assigned_tag=t,analysis_included=i) for d,t,i in [
            ('2026-01-11','aruco:1','true'),('2026-01-03','aruco:1','true'),
            ('2026-01-01','aruco:1','true'),('2026-01-03','aruco:1','true'),
            ('2025-12-01','aruco:1','false'),('2026-01-11','aruco:1','true'),
            ('2026-01-01','n8tag:1','true'),('2026-01-03','n8tag:1','true'),
            ('2026-01-01','aruco:2','true'),('2026-01-01','','true')]]
        result=recapture_intervals(rows)
        self.assertEqual(result, [
            dict(assigned_tag='aruco:1',first_capture_date='2026-01-01',recapture_date='2026-01-03',recapture_number=1,days_since_first_capture=2),
            dict(assigned_tag='aruco:1',first_capture_date='2026-01-01',recapture_date='2026-01-11',recapture_number=2,days_since_first_capture=10)])
        self.assertEqual(recapture_summary(result), dict(recaptured_aruco_tags=1,
            mean_recapture_days=6,min_recapture_days=2,max_recapture_days=10))
        self.assertIsNone(recapture_summary([])['mean_recapture_days'])
        self.assertEqual(recapture_intervals(rows[-2:]), [])

    def test_published_snapshot_preserved(self):
        rows=table('appearance_records_reviewed.csv'); reviews=table('published_reviews.csv')
        self.assertEqual(len(rows),1159);self.assertEqual(len({r['appearance_id'] for r in rows}),1159)
        self.assertEqual(sum(bool(r['review_status']) or r['domain_status']=='outside_domain' for r in rows),1130)
        self.assertEqual(sum(r['domain_status']=='outside_domain' for r in rows),10)
        self.assertEqual(sum(r['analysis_included']=='true' and not r['assigned_tag'] for r in rows),6)
        original={r['appearance_id']:r for r in reviews}
        for row in rows:
            source=original[row['appearance_id']]
            for f in ['reviewed_tag','review_status','review_note','domain_status']:
                self.assertEqual(row[f],source[f])
            self.assertEqual(row['source_assigned_tag'],source['assigned_tag'])
        daily=timeline(rows)
        self.assertEqual([{k:str(v) for k,v in r.items()} for r in daily],table('tagging_recapture_by_date.csv'))
        self.assertEqual(len(daily),28)
        self.assertEqual(daily[-1]['cumulative_unique_bees'],995)
        self.assertEqual(sum(r['recaptured_aruco_individuals'] for r in daily),143)
        self.assertEqual(daily[-1]['cumulative_aruco_recaptures'],143)

    def test_published_intervals_and_mean_reconcile(self):
        intervals=table('recapture_intervals.csv')
        self.assertEqual(len(intervals),143)
        self.assertEqual(len({(r['assigned_tag'],r['recapture_date']) for r in intervals}),143)
        self.assertEqual(len({r['assigned_tag'] for r in intervals}),119)
        # Reconcile independently against the unchanged identity histories.
        expected=set()
        for bee in table('bee_records_reviewed.csv'):
            if bee['tag_type']!='aruco':continue
            days=sorted(set(bee['appearance_dates'].split(';')))
            for day in days[1:]:
                expected.add((bee['bee_id'],days[0],day,(date.fromisoformat(day)-date.fromisoformat(days[0])).days))
        actual={(r['assigned_tag'],r['first_capture_date'],r['recapture_date'],int(r['days_since_first_capture'])) for r in intervals}
        self.assertEqual(actual,expected)
        durations=[int(r['days_since_first_capture']) for r in intervals]
        self.assertEqual(sum(durations),1040)
        counts=table('recapture_interval_counts.csv')
        self.assertEqual([int(r['days_since_first_capture']) for r in counts],list(range(1,46)))
        self.assertEqual(Counter(durations),Counter({int(r['days_since_first_capture']):int(r['recapture_events']) for r in counts}))
        summary=json.loads((ROOT/'docs/downloads/dataset_summary.json').read_text())
        self.assertAlmostEqual(summary['mean_recapture_days'],1040/143)
        self.assertEqual(summary['recaptured_aruco_tags'],119)
        self.assertEqual((summary['min_recapture_days'],summary['max_recapture_days']),(1,45))

    def test_unconfirmed_n8tags_remain_explicit(self):
        rows=table('appearance_records_reviewed.csv')
        unconfirmed=[r for r in rows if r['tag_type']=='n8tag' and not r['review_status'] and r['analysis_included']=='true']
        self.assertEqual(len(unconfirmed),27)
        self.assertTrue(all(r['assigned_tag'].startswith('n8tag:') for r in unconfirmed))

    def test_image_and_export_integrity(self):
        images=table('image_records_reviewed.csv')
        self.assertEqual(len(images),1543)
        self.assertEqual(len({r['image_id'] for r in images}),1543)
        self.assertEqual(sum(r['image_available']=='true' for r in images),1542)
        for im in images:
            self.assertEqual((ROOT/'docs/images'/im['image_file']).exists(),im['image_available']=='true')
        for file in (ROOT/'docs/downloads').glob('*.csv'):
            with file.open() as f:fields=next(csv.reader(f))
            self.assertFalse(set(fields)&{'path','source_paths','relative_path','source_path'})

    def test_daily_axis_and_missing_days(self):
        calendar=table('calendar_timeline.csv')
        self.assertEqual(len(calendar),88)
        self.assertEqual(sum(r['capture_records_present']=='true' for r in calendar),28)
        self.assertTrue(all(r['new_bees_tagged']=='' for r in calendar if r['capture_records_present']=='false'))
        cumulative_ids=cumulative_recaptures=0
        for row in calendar:
            if row['capture_records_present']=='true':
                cumulative_ids+=int(row['new_bees_tagged'])
                cumulative_recaptures+=int(row['recaptured_aruco_individuals'])
            self.assertEqual(int(row['cumulative_unique_bees']),cumulative_ids)
            self.assertEqual(int(row['cumulative_aruco_recaptures']),cumulative_recaptures)
        svg=(ROOT/'docs/downloads/tagging_and_recapture_graphs.svg').read_text()
        for row in calendar:self.assertIn(row['capture_date'],svg)


if __name__=='__main__':unittest.main()
