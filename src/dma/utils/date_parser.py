import time

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
    
    If the timestamp is not parsable, the current time will be returned.
    
    Parameters
    ----------
    timestamp : str | int
        The timestamp to parse.
    
    Returns
    -------
    float
        The timestamp as a float
    """
    if isinstance(timestamp, int):
        return time.time() - timestamp * 86400

    try:
        return float(timestamp)
    except ValueError:
        pass
    
    # check if timestamp is duration in days in format #d or #days
    if timestamp.endswith("d"):
        try:
            return time.time() - int(timestamp[:-1]) * 86400
        except ValueError:
            pass
    elif timestamp.endswith("days"):
        try:
            return time.time() - int(timestamp[:-4]) * 86400
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

    return time.time()