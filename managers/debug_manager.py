#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import os
import platform
import requests
import logging


class DebugManager(object):
    def __init__(self, title, version, max_logsize=1024 * 10):
        self.title = title
        self.log_filename = '%s.log' % title
        self.version = version
        self.max_logsize = max_logsize

        if os.path.exists(self.log_filename) and os.path.getsize(self.log_filename) > self.max_logsize:
            try:
                os.unlink(self.log_filename)
            except Exception as e:
                logging.error(e)
                pass

        logging.basicConfig(format='[%(asctime)s] %(levelname)s:\t\t%(message)s', filename=self.log_filename,
                            level=logging.DEBUG,
                            datefmt='%d.%m %H:%M:%S')
        logging.info('===============\n')

    def getReport(self, prefix=u'', affix=u'', extra=None):
        if not extra:
            extra = {}
        report = prefix
        report += u'==================START REPORT==================<br><br>'
        report += u'TITLE: %s<br>' % self.title
        report += u'VERSION: %s<br>' % self.version
        report += u'OS INFO: %s (%s)<br>' % (' '.join(platform.win32_ver()), " ".join(platform.architecture()))

        api_url = 'http://hastebin.com/documents'
        with open(self.log_filename) as f:
            url = 'http://hastebin.com/%(key)s' % requests.post(api_url, data=f.read()).json()
        report += u'LOG FILE: <a href="%s">%s</a> <br><br>' % (url, url)

        for arg in extra:
            report += u'%s: %s<br>' % (arg.upper(), extra[arg])

        report += u'<br>'
        report += u'===============!PLEASE FILL THIS FIELDS!==============<br><br>'
        report += u'SCREENSHOT: [please insert here your screenshot]<br>'
        report += u'STEPS TO REPRODUCE: [how you get it]<br>'
        report += u'RESULT: [what you have]<br>'
        report += u'EXPECTED RESULT: [what you expected]<br>'
        report += u'<br>'

        report += u'=================END REPORT===================='
        report += affix

        return report


def main():
    dm = DebugManager('transtes.log', '0.1.0')
    print(dm.getReport())


if __name__ == '__main__':
    main()
