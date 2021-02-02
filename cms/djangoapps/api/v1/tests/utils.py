def serialize_datetime(d):  # lint-amnesty, pylint: disable=missing-module-docstring
    return d.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
