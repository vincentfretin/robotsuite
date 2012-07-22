# -*- coding: utf-8 -*-
"""Python unittest test suite for Robot Framework"""

import unittest2 as unittest

import os
import string
import doctest
import StringIO
import unicodedata

import robot

last_status = None
last_message = None
rebot_datasources = []


# XXX: To be able to filter Robot Framework test cases, we monkeypatch
# robot.run.TestSuite (imported from robot.running.model.TestSuite)
# to just pass the first datasources as the test suite).

def TestSuite(datasources, settings):
    import robot.running.model
    suite = robot.running.model.RunnableTestSuite(datasources[0])
    suite.set_options(settings)
    robot.running.model._check_suite_contains_tests(
        suite, settings['RunEmptySuite'])
    return suite
robot.run.func_globals['TestSuite'] = TestSuite


def normalize(s):
    """Normalizes non-ascii characters to their closest ascii counterparts
    and replaces spaces with underscores"""
    whitelist = (' ' + string.ascii_letters + string.digits)

    if type(s) == str:
        s = unicode(s, 'utf-8', 'ignore')

    table = {}
    for ch in [ch for ch in s if ch not in whitelist]:
        if ch not in table:
            try:
                replacement = unicodedata.normalize('NFKD', ch)[0]
                if replacement in whitelist:
                    table[ord(ch)] = replacement
                else:
                    table[ord(ch)] = u'_'
            except:
                table[ord(ch)] = u'_'
    return s.translate(table).replace(u'_', u'').replace(u' ', u'_')


class RobotListener(object):
    """Robot Framework test runner test listener"""

    def end_test(self, status, message):
        global last_status
        global last_message
        last_status = status
        last_message = message


class RobotTestCase(unittest.TestCase):
    """Robot Framework single test suite"""

    def __init__(self, filename, module_relative=True, package=None,
                 source=None, name=None, outputdir=None,
                 setUp=None, tearDown=None, **kw):
        unittest.TestCase.__init__(self)

        filename = doctest._module_relative_path(package, filename)
        suite = robot.parsing.TestData(source=filename)

        def recurse(child_suite):
            if source and child_suite.source != source:
                child_suite.testcase_table.tests = []
            elif name:
                tests = child_suite.testcase_table.tests
                child_suite.testcase_table.tests =\
                    filter(lambda x: x.name == name, tests)
            for grandchild in getattr(child_suite, 'children', []):
                recurse(grandchild)
        recurse(suite)

        # set suite to be run bu runTest
        self._robot_suite = suite
        # set outputdir for log, report and screenshots
        self._robot_outputdir = outputdir
        # set test method name from the test name
        self._testMethodName = normalize(name or 'runTest')
        setattr(self, self._testMethodName, self.runTest)

        # set test fixture setup and teardown methods when given
        if setUp:
            setattr(self, 'setUp', setUp)
        if tearDown:
            setattr(self, 'tearDown', tearDown)

    def runTest(self):
        stdout = StringIO.StringIO()
        robot.run(self._robot_suite,
                  listener=('robotsuite.RobotListener',),
                  outputdir=self._robot_outputdir,
                  stdout=stdout)
        stdout.seek(0)

        # dump stdout on test failure or error
        if last_status != 'PASS':
            print stdout.read()

        # update concatenated robot log and report
        global rebot_datasources
        rebot_datasources.append(os.path.join(self._robot_outputdir,
                                              'output.xml'))
        robot.rebot(*rebot_datasources, stdout=stdout, output='output.xml',
                    logtitle='Summary', reporttitle='Summary', name='Summary')

        assert last_status == 'PASS', last_message


def RobotTestSuite(*paths, **kw):
    """Build up a test suite similarly to doctest.DocFileSuite"""

    suite = unittest.TestSuite()
    if kw.get('module_relative', True):
        kw['package'] = doctest._normalize_module(kw.get('package'))

    for path in paths:
        filename = doctest._module_relative_path(kw['package'], path)
        robot_suite = robot.parsing.TestData(source=filename)

        # split the robot suite into separate test cases

        outputdir = []

        def recurse(child_suite):
            suite_base = os.path.basename(child_suite.source)
            suite_dir = os.path.splitext(suite_base)[0]
            outputdir.append(suite_dir)
            for test in child_suite.testcase_table.tests:
                test_dir = normalize(test.name)
                outputdir.append(test_dir)
                suite.addTest(RobotTestCase(path, name=test.name,
                                            source=child_suite.source,
                                            outputdir='/'.join(outputdir),
                                            **kw))
                outputdir.pop()
            for grandchild in getattr(child_suite, 'children', []):
                recurse(grandchild)
            outputdir.pop()
        recurse(robot_suite)

    return suite
