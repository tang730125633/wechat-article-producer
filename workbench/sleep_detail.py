"""Validated native sleep segments; never infer stages from daily totals."""
import datetime as dt
from collections import defaultdict

from health_metrics import LOCAL_TZ, timestamp, text

STAGES = {'Awake': 'awake', 'REM': 'rem', 'Core': 'core', 'Deep': 'deep',
          'Asleep': 'asleep', 'Unspecified': 'asleep', 'In Bed': 'inBed',
          '清醒': 'awake', '快速动眼期': 'rem', '核心': 'core', '深度': 'deep'}


def parse_segments(rows):
    if len(rows) > 20000:
        raise ValueError('一次睡眠明细过多，请缩小导出日期范围')
    result = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('value') not in STAGES:
            raise ValueError('睡眠分期格式不支持')
        start, end = timestamp(row.get('startDate')), timestamp(row.get('endDate'))
        if not 0 < end - start <= 48 * 3600:
            raise ValueError('睡眠片段起止时间无效')
        source = text(row.get('source', ''), 300)
        result.add((source, start, end, STAGES[row['value']]))
    return sorted(result)


def store_segments(db, rows, now):
    # The phone automation sends complete, unbatched exports. Replace covered
    # source intervals so corrected stage boundaries do not leave ghost segments.
    groups = defaultdict(list)
    for source, start, end, stage in rows:
        groups[source].append((start, end, stage))
    changed = 0
    for source, values in groups.items():
        lower, upper = min(r[0] for r in values), max(r[1] for r in values)
        old = {tuple(r) for r in db.execute(
            'SELECT start,end,stage FROM sleep_segments WHERE source=? AND start<? AND end>?',
            (source, upper, lower))}
        if old == set(values):
            continue
        changed += len(old.symmetric_difference(values))
        db.execute('DELETE FROM sleep_segments WHERE source=? AND start<? AND end>?', (source, upper, lower))
        db.executemany('INSERT INTO sleep_segments VALUES (?,?,?,?,?)',
                       [(source, start, end, stage, now) for start, end, stage in values])
    return changed


def detail(db, record):
    result = {'sleep': record, 'segments': [], 'received': None, 'window': None}
    try:
        start = timestamp(record.get('inBedStart') or record.get('sleepStart'))
        end = timestamp(record.get('inBedEnd') or record.get('sleepEnd'))
        if not 0 < end - start <= 48 * 3600:
            return result
    except (ValueError, TypeError):
        return result
    result['window'] = {'start': start, 'end': end}
    for row in db.execute('SELECT * FROM sleep_segments WHERE start<? AND end>? ORDER BY start,end', (end, start)):
        result['segments'].append({'start': max(start, row['start']), 'end': min(end, row['end']),
                                   'stage': row['stage'], 'source': row['source']})
        result['received'] = max(result['received'] or 0, row['received'])
    return result


def latest_day(rows):
    return max((dt.datetime.fromtimestamp(r[2], LOCAL_TZ).date().isoformat() for r in rows), default=None)
