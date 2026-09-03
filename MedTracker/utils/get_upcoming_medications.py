from datetime import datetime
from django.utils import timezone
from ..models import MedicationSchedule, MedicationLog


def merge_sort_upcoming_meds(upcoming_meds):
    if len(upcoming_meds) <= 1:
        return upcoming_meds

    # Split the list into two halves
    mid = len(upcoming_meds) // 2
    left_half = merge_sort_upcoming_meds(upcoming_meds[:mid])
    right_half = merge_sort_upcoming_meds(upcoming_meds[mid:])

    # Merge the sorted halves
    return merge(left_half, right_half)


def merge(left, right):
    sorted_list = []
    while left and right:
        # Compare planned_time and append the smaller one
        if left[0]['planned_time'] <= right[0]['planned_time']:
            sorted_list.append(left.pop(0))
        else:
            sorted_list.append(right.pop(0))

    # Append the remaining elements 
    sorted_list.extend(left)
    sorted_list.extend(right)

    return sorted_list





def get_upcoming_medications(carehome):
    now = timezone.now()
    
    upcoming_meds = []

    # Get all residents in the care home
    residents = carehome.residents.all()

    # Get all medication schedules for these residents
    schedules = MedicationSchedule.objects.filter(
        resident__in=residents,
        is_active=True
    ).select_related(
        'resident', 
        'medication'
    ).prefetch_related('times')

    # Organize medications by time slots
    for schedule in schedules:
        for time_slot in schedule.times.all():
            med_time = timezone.make_aware(
                datetime.combine(now.date(), time_slot.time)
            )
            # time difference between when medication is due and the current time
            time_diff = med_time - now

            # If medication is more than 12 hours overdue, skip
            if time_diff.total_seconds() < -43200:  # 12 hours in seconds
                continue

            # Check if medication was already given today by checking the log
            was_given = MedicationLog.objects.filter(
                schedule=schedule,
                scheduled_time=time_slot,
                given_at__date=now.date()
            ).exists()

            # Calculate urgency level
            urgency = calculate_urgency(was_given, time_diff)

            upcoming_meds.append({
                'schedule': schedule,
                'time_slot': time_slot,
                'planned_time': med_time,
                'time_diff': time_diff,
                'urgency': urgency,
                'was_given': was_given
            })

    # Sort by time
    upcoming_meds = merge_sort_upcoming_meds(upcoming_meds)

    return upcoming_meds


def calculate_urgency(was_given, time_diff):
    if was_given:
        return 'given'
    thresholds = [
        (0, 'overdue'),
        (1800, 'urgent'),  # 30 minutes
        (3600, 'warning')  # 1 hour
    ]
    for limit, label in thresholds:
        if time_diff.total_seconds() < limit:
            return label
    return 'normal'