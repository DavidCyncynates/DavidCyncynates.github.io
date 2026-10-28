"""Conservative display state; dates never mutate or delete source records."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def cutoff(deadline):
    day = date.fromisoformat(deadline['date'])
    zone = deadline.get('timezone')
    clock = deadline.get('time')
    if zone:
        if clock:
            local = datetime.combine(day, time.fromisoformat(clock), ZoneInfo(zone))
        else:
            local = datetime.combine(day + timedelta(days=1), time.min, ZoneInfo(zone))
        return local.astimezone(timezone.utc)
    # No timezone was stated. Avoid hiding the listing before the date has ended
    # anywhere on Earth, but flag this approximation in every exported status.
    return datetime.combine(day + timedelta(days=1), time(12), timezone.utc)


def is_closing_stage(deadline):
    if deadline.get('stage') == 'national-application':
        # A later national date cannot reopen an earlier expired host cutoff,
        # but its own expiry closes the route even when the host date was soft.
        return deadline['kind'] == 'hard' and deadline.get('closesOpportunity', True)
    return deadline['kind'] in ('hard', 'eoi') and deadline.get('closesStage', True)


def display_state(job, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('An explicit timezone is required for the evaluation time')
    now = now.astimezone(timezone.utc)
    deadlines = [d for d in job.get('deadlines', []) if d.get('active', True)]
    closed = job.get('explicitClosed', False)
    expired = [d for d in deadlines if is_closing_stage(d) and now >= cutoff(d)]
    review_needed = job['verification'] != 'verified'
    milestones = [d for d in deadlines if d.get('stage') != 'national-application']
    upcoming = sorted([d for d in milestones if now < cutoff(d)], key=cutoff)
    past_soft = [d for d in milestones if not is_closing_stage(d) and now >= cutoff(d)]
    next_date = upcoming[0] if upcoming else None
    if closed:
        status = 'closed'
    elif expired:
        status = 'deadline-passed'
    elif review_needed:
        status = 'needs-review'
    elif past_soft:
        status = 'review-or-priority-date-passed'
    elif next_date:
        status = 'upcoming'
    elif job.get('openUntilFilled'):
        status = 'rolling'
    else:
        status = 'date-unconfirmed'
    days = (date.fromisoformat(next_date['date']) - now.date()).days if next_date else None
    color = 'red' if days is not None and days <= 7 else 'amber' if days is not None and days <= 30 else 'blue' if days is not None else 'neutral'
    return {
        'status': status,
        'reviewRequired': review_needed,
        'defaultEligible': not closed and not expired and not review_needed,
        'nextMilestone': next_date,
        'urgency': color,
        'hasPastPriorityOrReviewDate': bool(past_soft),
        'deadlineTimezoneUnconfirmed': any(not d.get('timezone') for d in deadlines),
        'dateOnlyExpiryPolicy': 'End of stated date in the stated timezone; if unknown, end of date anywhere on Earth. Consult the advertisement for exact submission time.',
        'evaluatedAt': now.isoformat(),
    }
