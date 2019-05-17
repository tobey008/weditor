#! /usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import
from __future__ import print_function

import os

import argparse
import signal
try:
    import Queue as queue
except BaseException:
    import queue
import webbrowser

import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.escape
from tornado import gen
from tornado.escape import json_encode
from tornado.log import enable_pretty_logging

# `pip install futures` for python2

from weditor.utils import create_shortcut
from weditor.view import (
    gqueue,
    MainHandler,
    VersionHandler,
    DeviceCheckHandler,
    DeviceCodeDebugHandler,
    DeviceConnectHandler,
    DeviceHierarchyHandler,
    DeviceInitHandler,
    DeviceScreenshotHandler,
    DeviceWSHandler)


try:
    enable_pretty_logging()
except BaseException:
    pass

__dir__ = os.path.dirname(os.path.abspath(__file__))
is_closing = False


def signal_handler(signum, frame):
    global is_closing
    print('exiting...')
    is_closing = True


def try_exit():
    global is_closing
    if is_closing:  # clean up here
        tornado.ioloop.IOLoop.instance().stop()
        print('exit success')


@gen.coroutine
def consume_queue():
    # print("Consume task queue")
    while True:
        try:
            (wself, value) = gqueue.get_nowait()
            wself.write_message(value)
        except queue.Empty:
            yield gen.sleep(.2)
        except Exception as e:
            print("Error in consume: " + str(e))
            yield gen.sleep(.5)


def make_app(debug):
    settings = {
        'static_path': os.path.join(__dir__, 'static'),
        'template_path': os.path.join(__dir__, 'templates'),
        'debug': debug,
    }
    application = tornado.web.Application([
        (r"/", MainHandler),
        (r"/api/v1/version", VersionHandler),
        (r"/api/v1/connect", DeviceConnectHandler),
        (r"/api/v1/devices/([^/]+)/screenshot", DeviceScreenshotHandler),
        (r"/api/v1/devices/([^/]+)/hierarchy", DeviceHierarchyHandler),
        (r"/api/v1/devices/([^/]+)/exec", DeviceCodeDebugHandler),
        (r"/ws/v1/build", DeviceWSHandler),
        (r"/api/v1/init", DeviceInitHandler),
        (r"/api/v1/check", DeviceCheckHandler)
    ], **settings)
    return application


def main(args):

    if args.shortcut:
        create_shortcut()
        return
    if not args.quiet:
        # webbrowser.open(url, new=2)
        webbrowser.open('http://localhost:' + str(args.port), new=2)
    application = make_app(args.debug)
    print('listen port', args.port)
    signal.signal(signal.SIGINT, signal_handler)
    application.listen(args.port)
    tornado.ioloop.PeriodicCallback(try_exit, 100).start()
    tornado.ioloop.IOLoop.instance().add_callback(consume_queue)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('-q', '--quiet', action='store_true',
                    help='quite mode, no open new browser')
    ap.add_argument('--debug', action='store_true', default=True,
                    help='open debug mode')
    ap.add_argument('--shortcut', action='store_true',
                    help='create shortcut in desktop')
    ap.add_argument('-p', '--port', type=int, default=17310,
                    help='local listen port for weditor')
    args = ap.parse_args()
    main(args=args)
