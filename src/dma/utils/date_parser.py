import time

DAY_IN_SECONDS = 60 * 60 * 24
WEEK_IN_SECONDS = DAY_IN_SECONDS * 7
MONTH_IN_SECONDS = DAY_IN_SECONDS * 30
YEAR_IN_SECONDS = DAY_IN_SECONDS * 365

# a function that tries to parse a timestamp from a string or int received from the evaluator
def parse_timestamp(timestamp: str | int) -> float:
    """
    Parse a timestamp from a string or int.
    If timestamp is an int, it will be interpreted as days before the current time.
    If timestamp is a string, it will be attemted to be parsed using the following formats:
    - DD-MM-YYYY
    - DD-MM
    - DD
    - YYYY
    - name of weekday
    - name of month
    
    If the timestamp is not parsable, -1 will be returned.
    
    Parameters
    ----------
    timestamp : str | int
        The timestamp to parse.
    
    Returns
    -------
    float
        The timestamp as a float
    """
    if isinstance(timestamp, int) or isinstance(timestamp, float):
        return time.time() - timestamp * DAY_IN_SECONDS
    
    if not isinstance(timestamp, str):
        return -1

    
    timestamp_lower = timestamp.lower().strip()
    if timestamp_lower in ["unknown", "n/a", "na", "none", "any", "always"]:
        return -1
    
    # check if timestamp is duration in days in format #d or #days
    if timestamp.endswith("d"):
        try:
            return time.time() - int(timestamp[:-1]) * DAY_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("days"):
        try:
            return time.time() - int(timestamp[:-4]) * DAY_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("day"):
        try:
            return time.time() - int(timestamp[:-3]) * DAY_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("w"):
        try:
            return time.time() - int(timestamp[:-1]) * WEEK_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("weeks"):
        try:
            return time.time() - int(timestamp[:-5]) * WEEK_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("week"):
        try:
            return time.time() - int(timestamp[:-4]) * WEEK_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("m"):
        try:
            return time.time() - int(timestamp[:-1]) * MONTH_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("months"):
        try:
            return time.time() - int(timestamp[:-6]) * MONTH_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("month"):
        try:
            return time.time() - int(timestamp[:-5]) * MONTH_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("y"):
        try:
            return time.time() - int(timestamp[:-1]) * YEAR_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("years"):
        try:
            return time.time() - int(timestamp[:-5]) * YEAR_IN_SECONDS
        except ValueError:
            pass
    elif timestamp.endswith("year"):
        try:
            return time.time() - int(timestamp[:-4]) * YEAR_IN_SECONDS
        except ValueError:
            pass

    try:
        return time.mktime(time.strptime(timestamp, "%d-%m-%Y"))
    except ValueError:
        pass

    try:
        return time.mktime(time.strptime(timestamp, "%d-%m"))
    except ValueError:
        pass

    try:
        return time.mktime(time.strptime(timestamp, "%d"))
    except ValueError:
        pass

    try:
        return time.mktime(time.strptime(timestamp, "%Y"))
    except ValueError:
        pass

    try:
        return time.mktime(time.strptime(timestamp, "%A"))
    except ValueError:
        pass

    try:
        return time.mktime(time.strptime(timestamp, "%B"))
    except ValueError:
        pass
    
    # some more last resort attempts
    try:
        return time.mktime(time.strptime(timestamp, "%Y-%m-%d"))
    except ValueError:
        pass
    
    try:
        return time.mktime(time.strptime(timestamp, "%Y-%m"))
    except ValueError:
        pass
    
    try:
        return time.mktime(time.strptime(timestamp, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        pass
    
    try:
        return time.mktime(time.strptime(timestamp, "%Y-%m-%d %H:%M"))
    except ValueError:
        pass
    
    seperators = [" ", "-", "/", "."]
    for sep in seperators:
        try:
            return time.mktime(time.strptime(timestamp, f"%Y{sep}%m{sep}%d"))
        except ValueError:
            pass
        
        try:
            return time.mktime(time.strptime(timestamp, f"%Y{sep}%m"))
        except ValueError:
            pass
        
        try:
            return time.mktime(time.strptime(timestamp, f"%Y{sep}%m{sep}%d %H:%M:%S"))
        except ValueError:
            pass
        
        try:
            return time.mktime(time.strptime(timestamp, f"%Y{sep}%m{sep}%d %H:%M"))
        except ValueError:
            pass
        
    # of this doesn't pass, I don't know what you want from me

    return -1