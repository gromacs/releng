import unittest

from releng.cmake import process_ctest_xml

from releng.test.utils import TestHelper

class TestRunBuild(unittest.TestCase):
    def setUp(self):
        self.helper = TestHelper(self)
        self.helper.add_input_file("Testing/TAG", """\
                YYYYMMDD-HHMM
                Experimental
                """)

    def test_CTestSuccess(self):
        self.helper.add_input_file("Testing/YYYYMMDD-HHMM/Test.xml", """\
                <Site>
                  <Testing>
                    <Test Status="passed">
                      <Name>Test1</Name>
                      <Results>
                        <NamedMeasurement name="Execution Time">
                          <Value>0.1</Value>
                        </NamedMeasurement>
                        <Measurement>
                          <Value>some output</Value>
                        </Measurement>
                      </Results>
                    </Test>
                  </Testing>
                </Site>
                """)
        process_ctest_xml(self.helper.executor, memcheck=False)
        self.helper.assertOutputFile("Testing/Temporary/CTest.xml", """\
                <testsuites><testsuite name="CTest"><testcase classname="CTest" name="Test1" time="0.1"><system-out>some output</system-out></testcase></testsuite></testsuites>""")

    def test_CTestFailure(self):
        self.helper.add_input_file("Testing/YYYYMMDD-HHMM/Test.xml", """\
                <Site>
                  <Testing>
                    <Test Status="failed">
                      <Name>Test1</Name>
                      <Results>
                        <NamedMeasurement name="Exit Code">
                          <Value>Failed</Value>
                        </NamedMeasurement>
                        <NamedMeasurement name="Execution Time">
                          <Value>0.1</Value>
                        </NamedMeasurement>
                        <Measurement>
                          <Value>some output</Value>
                        </Measurement>
                      </Results>
                    </Test>
                  </Testing>
                </Site>
                """)
        process_ctest_xml(self.helper.executor, memcheck=False)
        self.helper.assertOutputFile("Testing/Temporary/CTest.xml", """\
                <testsuites><testsuite name="CTest"><testcase classname="CTest" name="Test1" time="0.1"><failure message="Failed" /><system-out>some output</system-out></testcase></testsuite></testsuites>""")

    def test_CTestAsanFailure(self):
        self.helper.add_input_file("Testing/YYYYMMDD-HHMM/DynamicAnalysis.xml", """\
                <Site>
                  <DynamicAnalysis>
                    <Test Status="failed">
                      <Name>Test1</Name>
                      <Results>
                        <Defect type="SEGV">1</Defect>
                      </Results>
                      <Log>some output</Log>
                    </Test>
                  </DynamicAnalysis>
                </Site>
                """)
        process_ctest_xml(self.helper.executor, memcheck=True)
        self.helper.assertOutputFile("Testing/Temporary/CTest.xml", """\
                <testsuites><testsuite name="CTest_MemCheck"><testcase classname="CTest_MemCheck" name="Test1"><failure message="SEGV" /><system-out>some output</system-out></testcase></testsuite></testsuites>""")
