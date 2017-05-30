def format_timedelta(delta):
    """
    formatting timedelta object into human-readable string
    :param delta: timedelta object
    :return: formatted string
    """
    seconds = int(delta.total_seconds())
    return format_int(seconds)


def format_int(seconds):
    """
    source: http://stackoverflow.com/a/13756038 (with modifications)
    formatting seconds to human-readable string
    :param seconds: seconds to be reformatted
    :return: formatted string
    """
    periods = [
        ('year', 60 * 60 * 24 * 365),
        ('month', 60 * 60 * 24 * 30),
        ('day', 60 * 60 * 24),
        ('hour', 60 * 60),
        ('minute', 60),
        ('second', 1)
    ]

    strings = []
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            if period_value == 1:
                strings.append("%s %s" % (period_value, period_name))
            else:
                strings.append("%s %ss" % (period_value, period_name))

    if not strings:
        strings = ['0 seconds']

    return ", ".join(strings)
