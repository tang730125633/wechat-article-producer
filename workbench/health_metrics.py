"""Units and aggregation contracts shared by ingestion and the Mac reader."""
# Bounds validate transport data; they are not medical thresholds or user goals.
METRICS = {
    'step_count': ('Step Count', 'count', 'sum', {'count': (1, 0)}, 0, 1000000),
    'active_energy': ('Active Energy', 'kcal', 'sum', {'kcal': (1, 0), 'kJ': (1 / 4.184, 0)}, 0, 100000),
    'apple_exercise_time': ('Apple Exercise Time', 'min', 'sum', {'min': (1, 0), 's': (1 / 60, 0)}, 0, 1440),
    'apple_stand_hour': ('Apple Stand Hour', 'count', 'sum', {'count': (1, 0)}, 0, 24),
    'walking_running_distance': ('Walking + Running Distance', 'km', 'sum', {'km': (1, 0), 'mi': (1.609344, 0), 'm': (.001, 0)}, 0, 10000),
    'cycling_distance': ('Cycling Distance', 'km', 'sum', {'km': (1, 0), 'mi': (1.609344, 0), 'm': (.001, 0)}, 0, 10000),
    'flights_climbed': ('Flights Climbed', 'count', 'sum', {'count': (1, 0)}, 0, 10000),
    'time_in_daylight': ('Time in Daylight', 'min', 'sum', {'min': (1, 0), 's': (1 / 60, 0)}, 0, 1440),
    'resting_heart_rate': ('Resting Heart Rate', 'count/min', 'latest', {'count/min': (1, 0), 'bpm': (1, 0)}, 0, 1000),
    'heart_rate': ('Heart Rate', 'count/min', 'heart', {'count/min': (1, 0), 'bpm': (1, 0)}, 0, 1000),
    'heart_rate_variability': ('Heart Rate Variability', 'ms', 'mean', {'ms': (1, 0)}, 0, 1000000),
    'respiratory_rate': ('Respiratory Rate', 'count/min', 'mean', {'count/min': (1, 0)}, 0, 1000),
    'apple_sleeping_wrist_temperature': ('Apple Sleeping Wrist Temperature', 'degC', 'latest', {'degC': (1, 0), 'degF': (5 / 9, -32 * 5 / 9)}, -100, 200),
    'vo2_max': ('VO2 Max', 'ml/(kg·min)', 'latest', {'ml/(kg·min)': (1, 0)}, 0, 1000),
}

import datetime as dt
import math
import uuid

LOCAL_TZ = dt.timezone(dt.timedelta(hours=8))


def number(value, lower=0, upper=1e12):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError('健康指标包含无效数值')
    return value


def timestamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return number(value)
    if not isinstance(value, str):
        raise ValueError('健康记录时间格式错误')
    if len(value) == 10:
        return dt.datetime.combine(dt.date.fromisoformat(value), dt.time(), LOCAL_TZ).timestamp()
    try:
        parsed = dt.datetime.strptime(value, '%Y-%m-%d %H:%M:%S %z')
    except ValueError:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('健康记录时间需要时区')
    return parsed.timestamp()


def text(value, maximum=300):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError('健康记录文字格式错误')
    return value


def metric_record(name, unit, raw):
    if not isinstance(raw, dict):
        raise ValueError('请使用按天汇总的健康指标')
    title, canonical, mode, conversions, lower, upper = METRICS[name]
    if unit not in conversions:
        raise ValueError('健康指标单位不支持：' + name)
    day = dt.datetime.fromtimestamp(timestamp(raw.get('date')), LOCAL_TZ).date().isoformat()
    factor, offset = conversions[unit]
    value = raw.get('qty') if 'qty' in raw else raw.get('Avg')
    value = number(number(value, -1e9) * factor + offset, lower, upper)
    record = {'day': day, 'name': name, 'unit': canonical, 'value': round(value, 8), 'aggregation': mode}
    if name == 'heart_rate':
        low = number(raw.get('Min', value), lower, upper)
        high = number(raw.get('Max', value), lower, upper)
        if not low <= value <= high:
            raise ValueError('心率区间与均值不一致')
        record.update(min=low, max=high)
    source = raw.get('source')
    if isinstance(source, str):
        record['source'] = text(source)
    # Daily export dates identify buckets, not the instant a body measurement was taken.
    return record


def workout_record(raw):
    if not isinstance(raw, dict):
        raise ValueError('训练记录格式错误')
    identity = str(uuid.UUID(raw['id']))
    start, end = timestamp(raw['start']), timestamp(raw['end'])
    duration = number(raw['duration'], 0, 604800)
    if end < start or duration > end - start + 5:
        raise ValueError('训练时长与起止时间不一致')
    record = {'id': identity, 'day': dt.datetime.fromtimestamp(start, LOCAL_TZ).date().isoformat(),
              'name': text(raw['name'], 120), 'start': start, 'end': end, 'duration_seconds': duration}
    source = raw.get('source')
    if isinstance(source, dict):
        source = source.get('name')
    if isinstance(source, str):
        record['source'] = text(source)
    for field, target, conversions in [('activeEnergyBurned','energy_kcal',{'kcal':1,'kJ':1/4.184}),
                                      ('distance','distance_km',{'km':1,'mi':1.609344,'m':.001})]:
        if field not in raw:
            continue
        value = raw[field]
        if not isinstance(value, dict) or value.get('units') not in conversions:
            raise ValueError('训练记录单位不支持')
        record[target] = round(number(value.get('qty'), 0, 1e8) * conversions[value['units']], 8)
    # GPS routes, unrelated clinical data and provider metadata are deliberately not stored.
    return record
