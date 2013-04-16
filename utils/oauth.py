#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from functools import partial
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest, QNetworkCookieJar
from PyQt4.QtWebKit import QWebView, QWebSettings, QWebPage
from PyQt4.QtCore import QUrl, pyqtSignal, QObject, QString
from PyQt4.QtGui import QApplication
import json
import logging
import os
import sys
from TransTES import config_folder


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

    def __init__(self, parent, container, secrets, flow_args=None):
        QObject.__init__(self)
        self.parent = parent
        self.secrets = secrets
        self.storage = Storage(container)
        self.flow_args = flow_args if flow_args is not None else {}

        if self.storage.get():
            logging.info(u'Found oauth creds')
            self.creds = self.storage.get()
            self.http = self.creds.authorize(httplib2.Http(disable_ssl_certificate_validation=True))
        else:
            logging.info(u'OAuth creds not found. Auth or all requests will be unauthorized.')
            self.creds = False
            self.http = httplib2.Http(disable_ssl_certificate_validation=True)

    def auth(self):
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
        self.showBrowser(url)

    def step2(self):
        print(self.code, type(self.code))
        self.creds = self.flow.step2_exchange(self.code, http=self.http, cookie=self.cookie)
        logging.info(u'OAuth creds fetched')
        self.storage.put(self.creds)
        self.http = self.creds.authorize(httplib2.Http())
        self.creds_read.emit(self)

    def createRequest(self, op, request, data):
        reply = QNetworkAccessManager.createRequest(
            self.nm,
            op,
            request,
            data)
        return reply



    def showBrowser(self, url):
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
        self.browser.show()
        logging.debug(u'Auth browser opened')

    def handler(self, target):
        pass


class GDClient(BaseClient):
    def __init__(self, parent):
        secrets = {
            "client_id": '836414335615.apps.googleusercontent.com',
            "secret": 'G45aJ_akqQT-EPSw9AEeFQT8',
            "scope": 'https://www.googleapis.com/auth/drive.readonly',
            "callback": 'urn:ietf:wg:oauth:2.0:oob'
        }
        container = os.path.join(config_folder, 'gd')
        BaseClient.__init__(self, parent, container, secrets)
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
        return self.files[id]['fileSize']

    def getHeaders(self, id, arrived=0):
        size = self.getFileSize(id)
        headers = ['Range: bytes=%s-%s' % (arrived, size)]
        return headers


class GistClient(BaseClient):
    def __init__(self, parent):
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
        BaseClient.__init__(self, parent, container, secrets, flow_args)
        self.gists = {}

    def fetchGistInfo(self, id):
        resp, content = self.http.request('https://api.github.com/gists/%s' % id)
        content = json.loads(content)
        if resp['status'] != '200':
            print(resp, content)
        self.gists[id] = content
        return content

    def createRequest(self, op, request, data):
        url = str(request.url().toString().toUtf8())
        # print(url, request.rawHeaderList())
        if url.startswith('http://localhost'):
            for c in self.cj.allCookies():
                if c.name() == '_gh_sess':
                    # print(dir(c.value()))
                    self.cookie = str(QString(c.toRawForm()).toUtf8())
                    print(self.cookie)
            url, code = url.split('=')
            self.code = code
            self.token_read.emit(self.code)
        reply = QNetworkAccessManager.createRequest(
            self.nm,
            op,
            request,
            data)
        return reply


    def getFile(self, id, name):
        url = self.gists[id]['files'][name]['raw_url']
        code, content = self.http.request(url)
        return content



def main():
    qtapp = QApplication(sys.argv)

    client = GistClient(None)
    # client = GDClient(None)
    gid = '5338904'
    gname = 'Skywind.yml'

    # fid = '0B8F9egY3lyGdUUhtZnVydmJIVjQ'


    def afterAuth(client):
        client.fetchGistInfo(gid)
        c = client.getFile(gid, gname)
        # c = client.fetchFileInfo(fid)
        print(c)
        sys.exit()

    if not client.creds:
        client.creds_read.connect(afterAuth)
        client.auth()
    else:
        afterAuth(client)

    qtapp.exec_()


if __name__ == '__main__':
    main()
