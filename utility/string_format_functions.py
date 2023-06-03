from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU
from datetime import datetime, timedelta

def get_time_since_delta(delta: timedelta) -> str:
    now = datetime.utcnow()
    timestamp = int((now + delta).timestamp())
    return f"<t:{timestamp}:R>"



def explain_rrule(rrule_obj:rrule):
    freq_mapping = {
        DAILY: 'daily',
        WEEKLY: 'weekly',
        MONTHLY: 'monthly',
    }
    weekday_mapping = [
        "Monday",  
        "Tuesday",  
        "Wednesday",
        "Thursday", 
        "Friday", 
        "Saturday", 
        "Sunday"    
    ]

    freq = freq_mapping.get(rrule_obj._freq, 'unknown')
    start_date = rrule_obj._dtstart.strftime("%Y-%m-%d")
    end_date = rrule_obj._until.strftime("%Y-%m-%d") if rrule_obj._until else 'never'
    interval = rrule_obj._interval
    
    weekdays='any'
    if rrule_obj._byweekday:
        weeks=list(rrule_obj._byweekday)
        weekdays=''
        for e,w in enumerate(weeks):
            if e==len(weeks)-1:
                weekdays+="and "
            weekdays +=  weekday_mapping[w]
            if e<len(weeks)-1:
                weekdays+=", "
    else:
        pass
    next_occurrences=[]
    now=datetime.now()
    for _ in range(4):
        next_timestamp = rrule_obj.after(now)
        if next_timestamp:
            next_occurrences.append(f"<t:{int(next_timestamp.timestamp())}:F>")
            now = next_timestamp
    time = rrule_obj._dtstart.strftime("%H:%M")

    # Interval explanation
    interval_description = ""
    if freq==1:
        interval_description = ""
    elif freq == DAILY:
        interval_description = f"every {freq} days"
    elif freq == WEEKLY:
        interval_description = f"every {interval} weeks"
    elif freq == MONTHLY:
        interval_description = f"every {interval} months"

    description = f"Frequency: {freq}\n"
    description += f"Start Date: {start_date}\n"
    if end_date!='never':
        description += f"End Date: {end_date}\n"
    description += f"Interval: {interval}\n"
    if weekdays:
        description += f"Weekdays: {weekdays}\n"
    description += f"Time: {time}\n"
    description += f"Next Occurrences: {', '.join(next_occurrences)}"

    sentence=""
    sentence = f"The rule is set to run {freq} starting from {start_date}"
    if end_date != 'never':
        sentence += f" until {end_date}"
    sentence += f", {interval_description}"
    if weekdays!='any':
        sentence += f" on {weekdays}, "
    sentence += f" at {time}"
    sentence += f". \n It will run next on {', '.join(next_occurrences)}."

    return description, sentence
