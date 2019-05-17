from adb.client import Client
import os,sys
import hashlib
import six
client = Client()

def devices():
    return client.devices()


def init():
    pass

def install():
    pass


def create_shortcut():
    if os.name != 'nt':
        sys.exit("Only valid in Windows")

    import pythoncom
    from win32com.shell import shell
    from win32com.shell import shellcon
    # Refs
    # - https://github.com/pearu/iocbio/blob/master/installer/utils.py
    # - https://blog.csdn.net/thundor/article/details/5968581
    ilist = shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_DESKTOP)
    dtpath = shell.SHGetPathFromIDList(ilist).decode('utf-8')

    shortcut = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink, None,
        pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink)
    launch_path = sys.executable
    shortcut.SetPath(launch_path)
    shortcut.SetArguments("-m weditor")
    shortcut.SetDescription(launch_path)
    shortcut.SetIconLocation(sys.executable, 0)
    shortcut.QueryInterface(
        pythoncom.IID_IPersistFile).Save(dtpath + "\\WEditor.lnk", 0)
    print("Shortcut created. " + dtpath + "\\WEditor.lnk")


def tostr(s, encoding='utf-8'):
    if six.PY2:
        return s.encode(encoding)
    if isinstance(s, bytes):
        return s.decode(encoding)
    return s


def read_file_content(filename, default=''):
    if not os.path.isfile(filename):
        return default
    with open(filename, 'rb') as f:
        return f.read()


def write_file_content(filename, content):
    with open(filename, 'w') as f:
        f.write(content.encode('utf-8'))


def sha_file(path):
    sha = hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            sha.update(data)
    return sha.hexdigest()


def virt2real(path):
    return os.path.join(os.getcwd(), path.lstrip('/'))


def real2virt(path):
    return os.path.relpath(path, os.getcwd()).replace('\\', '/')