#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from urlparse import parse_qs
from functools import partial
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest, QNetworkCookieJar
from PyQt4.QtWebKit import QWebView, QWebSettings, QWebPage
from PyQt4.QtCore import QUrl, pyqtSignal, QObject, QString, QSize
from PyQt4.QtGui import QApplication
import json
import logging
import os
import sys
from urlparse import urlparse
from Launcher import config_folder


__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.0'

from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
import httplib2


class LimitExceeded(Exception):
    pass


class BaseClient(QObject):
    token_read = pyqtSignal(str)
    creds_read = pyqtSignal(object)
    error = pyqtSignal(Exception)
    force_unauth = False

    def __init__(self, container, secrets, flow_args=None):
        QObject.__init__(self)
        self.secrets = secrets
        self.storage = Storage(container)
        self.flow_args = flow_args if flow_args is not None else {}

        if self.storage.get():
            logging.info(u'Found oauth creds')
            self.creds = self.storage.get()
            self._http = self.creds.authorize(httplib2.Http(disable_ssl_certificate_validation=True))
        else:
            logging.info(u'OAuth creds not found. Auth or all requests will be unauthorized.')
            self.creds = False
            self._http = httplib2.Http(disable_ssl_certificate_validation=True)

    def auth(self, size=None):
        logging.info(u'Trying to get new oauth creds')
        self.flow = OAuth2WebServerFlow(
            self.secrets['client_id'],
            self.secrets['secret'],
            self.secrets['scope'],
            redirect_uri=self.secrets['callback'],
            **self.flow_args
        )
        url = self.flow.step1_get_authorize_url()
        self.token_read.connect(self.step2)
        self.showBrowser(url, size)

    def step2(self):
        print(self.code, type(self.code))
        self.creds = self.flow.step2_exchange(self.code, http=self.http, cookie=self.cookie)
        logging.info(u'OAuth creds fetched')
        self.storage.put(self.creds)
        self._http = self.creds.authorize(httplib2.Http(disable_ssl_certificate_validation=True))
        self.creds_read.emit(self)

    def createRequest(self, op, request, data):
        reply = QNetworkAccessManager.createRequest(
            self.nm,
            op,
            request,
            data)
        return reply

    @property
    def http(self):
        if not self.force_unauth:
            return self._http
        else:
            return httplib2.Http(disable_ssl_certificate_validation=True)


    def showBrowser(self, url, size=None):
        self.browser = QWebView()
        QWebSettings.globalSettings().setAttribute(QWebSettings.JavascriptEnabled, True)
        QWebSettings.globalSettings().setAttribute(QWebSettings.DeveloperExtrasEnabled, True)

        page = QWebPage()
        self.cookie = None
        self.cj = QNetworkCookieJar()
        self.nm = QNetworkAccessManager()
        self.nm.setCookieJar(self.cj)
        self.nm.createRequest = self.createRequest
        page.setNetworkAccessManager(self.nm)
        self.browser.setPage(page)

        self.browser.load(QUrl.fromEncoded(url))
        self.browser.titleChanged.connect(self.handler)
        self.browser.urlChanged.connect(self.handler)
        if size is not None:
            self.browser.resize(size)
        self.browser.show()
        logging.debug(u'Auth browser opened')

    def handler(self, target):
        pass


class GDClient(BaseClient):
    def __init__(self):
        secrets = {
            "client_id": '836414335615.apps.googleusercontent.com',
            "secret": 'G45aJ_akqQT-EPSw9AEeFQT8',
            "scope": 'https://www.googleapis.com/auth/drive.readonly',
            "callback": 'urn:ietf:wg:oauth:2.0:oob'
        }
        container = os.path.join(config_folder, 'gd')
        BaseClient.__init__(self, container, secrets)
        self.files = {}

    def handler(self, target):
        if not isinstance(target, QUrl):
            title = str(target.toUtf8())
            if title.startswith('Success code='):
                self.code = title[len('Success code='):]
                self.browser.hide()
                print(self.code)
                self.token_read.emit(self.code)

    def fetchFileInfo(self, id):
        resp, content = self.http.request("https://www.googleapis.com/drive/v2/files/%s" % id)
        content = json.loads(content)
        if resp['status'] != '200':
            print(resp, content)
            raise LimitExceeded(content['error']['message'])
        self.files[id] = content
        return content

    def getDirectLink(self, id):
        return self.files[id]['downloadUrl']

    def getFileName(self, id):
        return self.files[id]['originalFilename']

    def getFileSize(self, id):
        return int(self.files[id]['fileSize'])

    def getHeaders(self, id, arrived=0):
        size = self.getFileSize(id)
        headers = ['Range: bytes=%s-%s' % (arrived, size), 'Authorization: Bearer %s' % self.creds.access_token]
        return headers


class GDFile(object):
    client = GDClient()

    def __init__(self, url):
        self.url = url
        parsed = urlparse(url)
        try:
            self.id = parse_qs(parsed.query)['id'][0]
        except KeyError:
            self.id = url.split('/')[-1]
            if self.id == 'edit':
                self.id = url.split('/')[-2]

        self.client.fetchFileInfo(self.id)

    def getDirectLink(self):
        return self.client.getDirectLink(self.id)

    def getFileName(self):
        return self.client.getFileName(self.id)

    def getFileSize(self):
        return self.client.getFileSize(self.id)

    def getHeaders(self, arrived=0):
        return self.client.getHeaders(self.id, arrived)


class GistClient(BaseClient):
    def __init__(self):
        secrets = {
            "client_id": 'bc72cc629b7af03eccf0',
            "secret": '50264a7cb5ea55fdd38e1e7d2ba08290b570edce',
            "scope": 'gist',
            "callback": None
        }
        flow_args = {
            'auth_uri': "https://github.com/login/oauth/authorize",
            'token_uri': "https://github.com/login/oauth/access_token",
            'revoke_uri': "https://github.com/login/oauth/access_token"
        }
        container = os.path.join(config_folder, 'gists')
        BaseClient.__init__(self, container, secrets, flow_args)
        self.gists = {}

    def getDirectLink(self, id, name):
        url = self.gists[id]['files'][name]['raw_url']
        return url

    def fetchGistInfo(self, id):
        resp, content = self.http.request('https://api.github.com/gists/%s' % id)
        content = json.loads(content)
        if resp['status'] != '200':
            print(resp, content)
            raise LimitExceeded(content['error']['message'])
        self.gists[id] = content
        return content

    def createRequest(self, op, request, data):
        url = str(request.url().toString().toUtf8())
        # print(url, request.rawHeaderList())
        if url.startswith('http://localhost'):
            # for c in self.cj.allCookies():
            #     if c.name() == '_gh_sess':
            #         self.cookie = str(QString(c.toRawForm()).toUtf8())
            #         print(self.cookie)
            url, code = url.split('=')
            self.code = code
            self.browser.hide()
            self.token_read.emit(self.code)
        reply = QNetworkAccessManager.createRequest(
            self.nm,
            op,
            request,
            data)
        return reply

    def getLimits(self):
        resp, content = self.http.request('https://api.github.com/rate_limit')
        return json.loads(content)


    def getFile(self, id, name):
        url = self.gists[id]['files'][name]['raw_url']
        code, content = self.http.request(url)
        return content


def main():
    qtapp = QApplication(sys.argv)

    client = GistClient()
    # client = GDClient()
    gid = '5338904'
    gname = 'Skywind.yml'

    # fid = '0B8F9egY3lyGdUUhtZnVydmJIVjQ'


    def afterAuth(client):
        # client.force_unauth = True
        client.fetchGistInfo(gid)
        # c = client.getFile(gid, gname)
        # c = client.fetchFileInfo(fid)
        c = client.getLimits()
        print(c)
        sys.exit()

    if not client.creds:
        client.creds_read.connect(afterAuth)
        client.auth(QSize(1000, 800))
    else:
        afterAuth(client)

    qtapp.exec_()


if __name__ == '__main__':
    main()
