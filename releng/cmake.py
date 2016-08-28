"""
Helper routines for parsing CMake-related stuff.
"""
import os.path
import re
import xml.etree.ElementTree as ET

from common import BuildError, ConfigurationError

def read_cmake_variable_file(executor, path):
    """Reads a file with CMake variable declarations (set commands).

    Args:
        path (str): Path to the file to read.

    Returns:
        Dict: variables found from the file, with their values.
    """
    values = dict()
    set_re = r'(?i)SET\((\w+)\s*"(.*)"\)\s*'
    for line in executor.read_file(path):
        match = re.match(set_re, line)
        if match:
            values[match.group(1)] = match.group(2)
    return values

def read_cmake_minimum_version(executor, root):
    version_re = r'(?i)cmake_minimum_required\s*\(\s*VERSION\s+([\d.]+)\s*\)'
    path = os.path.join(root, 'CMakeLists.txt')
    if os.path.isfile(path):
        for line in executor.read_file(path):
            match = re.match(version_re, line)
            if match:
                return match.group(1)
        raise ConfigurationError('Could not parse minimum required CMake version from CMakeLists.txt')
    return None

def get_cmake_version(cmd_runner, cmake_executable):
    version_re = 'cmake version\s*([\d.]+)'
    output = cmd_runner.check_output([cmake_executable, '--version'])
    match = re.match(version_re, output)
    if match:
        return match.group(1)
    raise ConfigurationError('Could not parse CMake version:\n' + output)

def process_ctest_xml(executor, memcheck):
    tag = _read_ctest_tag_name(executor)
    xml_name, test_xpath, suite_name = _get_properties(memcheck)
    ctest_root = _read_ctest_xml(executor, tag, xml_name)
    junit_root = ET.Element('testsuites')
    junit_suite = ET.SubElement(junit_root, 'testsuite', {'name': suite_name})
    for test in ctest_root.findall(test_xpath):
        if memcheck:
            _create_junit_testcase_memcheck(test, junit_suite, suite_name)
        else:
            _create_junit_testcase(test, junit_suite, suite_name)
    contents = ET.tostring(junit_root)
    executor.write_file('Testing/Temporary/CTest.xml', contents)

def _read_ctest_tag_name(executor):
    lines = list(executor.read_file('Testing/TAG'))
    if len(lines) < 1:
        raise BuildError('CTest did not produce content in a TAG file')
    return lines[0].strip()

def _get_properties(memcheck):
    if memcheck:
        # TODO: If the tests pass, they do not create Test entries at all (at
        # least, not for ASAN)...
        # It would be nice to still get the same list of tests always.
        return 'DynamicAnalysis.xml', './DynamicAnalysis/Test', 'CTest_MemCheck'
    else:
        return 'Test.xml', './Testing/Test', 'CTest'

def _read_ctest_xml(executor, tag, xml_name):
    xml_path = os.path.join('Testing', tag, xml_name)
    xml_lines = executor.read_file(xml_path)
    return ET.fromstring(''.join(xml_lines))

def _create_junit_testcase(test, parent, suite_name):
    name = test.find('Name').text
    time = _get_named_measurement(test, 'Execution Time')
    passed = (test.get('Status') == 'passed')
    attrs = {'name': name, 'classname': suite_name, 'time': time}
    junit_case = ET.SubElement(parent, 'testcase', attrs)
    if not passed:
        reason = _get_named_measurement(test, 'Exit Code')
        failure = ET.SubElement(junit_case, 'failure', {'message': reason})
    output = ET.SubElement(junit_case, 'system-out')
    output.text = test.find('./Results/Measurement/Value').text

def _get_named_measurement(test, name):
    return test.find("./Results/NamedMeasurement[@name='{0}']/Value".format(name)).text

def _create_junit_testcase_memcheck(test, parent, suite_name):
    name = test.find('Name').text
    passed = (test.get('Status') == 'passed')
    attrs = {'name': name, 'classname': suite_name}
    junit_case = ET.SubElement(parent, 'testcase', attrs)
    if not passed:
        # TODO: This will produce an empty message if the test fails normally,
        # not because of an ASAN error...
        defects = test.findall('./Results/Defect')
        reason = ', '.join([x.get('type') for x in defects])
        failure = ET.SubElement(junit_case, 'failure', {'message': reason})
    output = ET.SubElement(junit_case, 'system-out')
    output.text = test.find('Log').text
