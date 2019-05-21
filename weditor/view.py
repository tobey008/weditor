# -*- coding: utf-8 -*-
import sys
import platform
import time
import json
import os
import traceback
import uuid
from io import BytesIO
import base64
import tornado.web
import tornado.websocket
import tornado.gen
try:
    import subprocess32 as subprocess
    from subprocess32 import PIPE
except BaseException:
    import subprocess
    from subprocess import PIPE
try:
    import Queue as queue
except BaseException:
    import queue
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor
from weditor.utils import tostr
from weditor import uidumplib


cached_devices = {}
gqueue = queue.Queue()

__version__ = '0.0.3'


class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header("Access-Control-Allow-Credentials",
                        "true")  # allow cookie
        self.set_header('Access-Control-Allow-Methods',
                        'POST, GET, PUT, DELETE, OPTIONS')

    def options(self, *args):
        self.set_status(204)  # no body
        self.finish()


class VersionHandler(BaseHandler):
    def get(self):
        ret = {
            'name': __version__,
        }
        self.write(ret)


class DeviceScreenshotHandler(BaseHandler):
    def get(self, id):
        print("SN", id)
        try:
            d = cached_devices.get(id)
            buffer = BytesIO()
            d.screenshot().convert("RGB").save(buffer, format='JPEG')
            b64data = base64.b64encode(buffer.getvalue())
            response = {
                "type": "jpeg",
                "encoding": "base64",
                "data": b64data.decode('utf-8'),
            }
            self.write(response)
        except EnvironmentError as e:
            traceback.print_exc()
            self.set_status(430, "Environment Error")
            self.write({
                "description": str(e)
            })


class MainHandler(BaseHandler):
    def get(self):
        self.render("index.html")


class DeviceWSHandler(tornado.websocket.WebSocketHandler):
    executor = ThreadPoolExecutor(max_workers=4)
    # proc = None

    def open(self):
        print("Websocket opened")
        self.proc = None

    def check_origin(self, origin):
        return True

    @run_on_executor
    def _run(self, device_url, code):
        """
        Thanks: https://gist.github.com/mosquito/e638dded87291d313717
        """
        try:

            print("DEBUG: run code\n%s" % code)
            env = os.environ.copy()
            env['UIAUTOMATOR_DEBUG'] = 'true'
            if device_url and device_url != 'default':
                env['ATX_CONNECT_URL'] = tostr(device_url)
            start_time = time.time()

            self.proc = subprocess.Popen(
                [sys.executable, "-u"], env=env, stdout=PIPE, stderr=subprocess.STDOUT, stdin=PIPE)
            self.proc.stdin.write(code)
            self.proc.stdin.close()

            for line in iter(self.proc.stdout.readline, b''):
                print("recv subprocess:", repr(line))
                if line is None:
                    break
                gqueue.put((self, {"buffer": line.decode('utf-8')}))
            print("Wait exit")
            exit_code = self.proc.wait()
            duration = time.time() - start_time
            ret = {
                "buffer": "",
                "result": {
                    "exitCode": exit_code,
                    "duration": int(duration) *
                    1000}}
            gqueue.put((self, ret))
            time.sleep(3)  # wait until write done
        except Exception:
            traceback.print_exc()

    @tornado.gen.coroutine
    def on_message(self, message):
        jdata = json.loads(message)
        if self.proc is None:
            code = jdata['content']
            device_url = jdata.get('deviceUrl')
            yield self._run(device_url, code.encode('utf-8'))
            self.close()
        else:
            try:
                self.proc.terminate()
                # on Windows, kill is alais of terminate()
                if platform.system() == 'Windows':
                    return
                yield tornado.gen.sleep(0.5)
                if self.proc.poll():
                    return
                yield tornado.gen.sleep(1.2)
                if self.proc.poll():
                    return
                print("Force to kill")
                self.proc.kill()
            except WindowsError as e:
                print("Kill error on windows " + str(e))

    def on_close(self):
        print("Websocket closed")


class _AndroidDevice(object):
    def __init__(self, device_url):
        import uiautomator2 as u2
        d = u2.connect(device_url)
        if d.agent_alive:
            self._d = d
            return
        raise Exception("设备连接失败...")

    def screenshot(self):
        return self._d.screenshot()

    def dump_hierarchy(self):
        return uidumplib.get_android_hierarchy(self._d)

    @property
    def device(self):
        return self._d


class _AppleDevice(object):
    def __init__(self, device_url):
        import wda
        c = wda.Client(device_url)

        self._client = c
        self.__scale = c.session().scale

    def screenshot(self):
        return self._client.screenshot(format='pillow')

    def dump_hierarchy(self):
        return uidumplib.get_ios_hierarchy(self._client, self.__scale)

    @property
    def device(self):
        return self._client


class _GameDevice(object):
    def __init__(self, device_url):
        import neco
        d = neco.connect(device_url)
        self._d = d

    def screenshot(self):
        return self._d.screenshot()

    def dump_hierarchy(self):
        return self._d.dump_hierarchy()

    @property
    def device(self):
        return self._d


# todo:连接手机
class DeviceConnectHandler(BaseHandler):
    def post(self):
        platform = self.get_argument("platform").lower()
        device_url = self.get_argument("deviceUrl")
        id = str(uuid.uuid4())
        socket_url = ""
        try:
            if platform == 'android':
                d = _AndroidDevice(device_url)
                print(d)
                d.platform = 'android'
                cached_devices[id] = d
                socket_url = d._d._host + ":" + str(d._d._port)
            elif platform == 'ios':
                cached_devices[id] = _AppleDevice(device_url)
            else:
                cached_devices[id] = _GameDevice(device_url or "localhost")
                # import neco
                # d = neco.connect(device_url or 'localhost')
                # cached_devices[id] = d
        except Exception as e:
            #self.set_status(430, "Connect Error")
            print(e)
            self.write({
                "success": False,
                # "description": traceback.format_exc().encode('utf-8'),
            })
        else:
            self.write({
                "deviceId": id,
                'success': True,
                "socket_url": socket_url,
            })


class DeviceHierarchyHandler(BaseHandler):
    def get(self, id):
        d = cached_devices.get(id)
        self.write(d.dump_hierarchy())


# todo:初始化本地设备和连接本地手机
class DeviceInitHandler(BaseHandler):
    def get(self):
        from uiautomator2.__main__ import _init_with_serial
        from uiautomator2.version import __apk_version__, __atx_agent_version__
        print("start...")
        from adb.client import Client as AdbClient
        client = AdbClient()
        devices = client.devices()
        for d in devices:
            print(d.serial)
        if not devices:
            self.write({
                "success": False,
                "serial": "",
                "deviceId": "",

            })
            return
        for d in devices:
            serial = d.get_serial_no()
            if d.get_state() != 'device':
                print("Skip invalid device: %s %s", serial,
                      d.get_state())
                continue
            print("Init device %s", serial)
            # todo:初始化代码优化
            try:
                device = _AndroidDevice(serial)

            except BaseException:
                _init_with_serial(
                    serial=serial,
                    apk_version=__apk_version__,
                    agent_version=__atx_agent_version__,
                    server=None,
                    reinstall=False)
                device = _AndroidDevice(serial)
            # serial = device._d.wlan_ip + ":7912"
            id = str(uuid.uuid4())
            cached_devices[id] = device
            socket_url = device._d._host + ":" + str(device._d._port)
            self.write({
                "success": True,
                "serial": serial,
                "deviceId": id,
                "socket_url": socket_url

            })
            return


class DeviceCodeDebugHandler(BaseHandler):
    def post(self, id):
        d = cached_devices.get(id)
        code = self.get_argument('code')
        start = time.time()
        buffer = BytesIO()
        sys.stdout = buffer
        sys.stderr = buffer

        is_eval = True
        try:
            compiled_code = compile(code, "<string>", "eval")
        except SyntaxError:
            is_eval = False
            compiled_code = compile(code, "<string>", "exec")
        try:
            if is_eval:
                ret = eval(code, {'d': d._d})
                buffer.write((">>> " + repr(ret) + "\n").encode('utf-8'))
            else:
                exec(compiled_code, {'d': d._d})
        except BaseException:
            buffer.write(traceback.format_exc().encode('utf-8'))
        finally:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
        self.write({
            "success": True,
            "duration": int((time.time() - start) * 1000),
            "content": buffer.getvalue().decode('utf-8'),
        })


class DeviceCheckHandler(BaseHandler):
    def get(self):
        from adb.client import Client as AdbClient
        client = AdbClient()
        devices = client.devices()
        ret = {"success": True, "devices": []}
        if not devices:
            self.write({"success": False})
            return
        for device in devices:
            data = {}
            data["serial"] = device.serial
            data["status"] = device.get_state()
            if device.shell("getprop ro.arch").strip() == "x86":
                data["emulator"] = True
            else:
                data["emulator"] = False
            ret["devices"].append(data)
        self.write(ret)
