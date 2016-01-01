"""
Misc. utility functions.
"""

def read_property_file(executor, path):
    """Reads a property file written by write_property_file().

    Args:
        executor (Executor): Executor to use for reading.
        path (str): Path to the file to read.

    Returns:
        Dict: values read from the file.
    """
    values = dict()
    for line in executor.read_file(path):
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values

def write_property_file(executor, path, values):
    """Writes a property file at given path.

    Args:
        executor (Executor): Executor to use for writing.
        path (str): Path to the file to write.
        values (Dict): Dictionary of key/value pairs to write.
    """
    contents = ''.join(['{0} = {1}\n'.format(key, value) for key, value in values.iteritems() if value is not None])
    executor.write_file(path, contents)
