# coding: utf-8

import re
import xml.dom.minidom
import uuid

def parse_bounds(text):
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', text)
    if m is None:
        return None
    (lx, ly, rx, ry) = map(int, m.groups())
    return dict(x=lx, y=ly, width=rx-lx, height=ry-ly)


def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")


def str2int(v):
    return int(v)


def convstr(v):
    return v
    # return v.encode('utf-8')


__alias = {
    'class': 'className',
    'resource-id': 'resourceId',
    'content-desc': 'description',
    'long-clickable': 'longClickable',
    'bounds': 'rect',
}

__parsers = {
    # Android
    'rect': parse_bounds,
    'text': convstr,
    'className': convstr,
    'resourceId': convstr,
    'package': convstr,
    'checkable': str2bool,
    'scrollable': str2bool,
    'focused': str2bool,
    'clickable': str2bool,
    'selected': str2bool,
    'longClickable': str2bool,
    'focusable': str2bool,
    'password': str2bool,
    'index': int,
    'description': convstr,
    # iOS
    'name': convstr,
    'label': convstr,
    'x': str2int,
    'y': str2int,
    'width': str2int,
    'height': str2int,
    # iOS && Android
    'enabled': str2bool,
}


def parse_uiautomator_node(node):
    ks = {}
    for key, value in node.attributes.items():
        key = __alias.get(key, key)
        f = __parsers.get(key)
        if value is None:
            ks[key] = None
        elif f:
            ks[key] = f(value)
    if 'bounds' in ks:
        lx, ly, rx, ry = map(int, ks.pop('bounds'))
        ks['rect'] = dict(x=lx, y=ly, width=rx-lx, height=ry-ly)
    return ks


def get_android_hierarchy(d):
    """
    Returns:
        JSON object
    """
    page_xml = d.dump_hierarchy(compressed=False, pretty=False).encode('utf-8')
    dom = xml.dom.minidom.parseString(page_xml)
    root = dom.documentElement

    def travel(node):
        # print(node)
        if node.attributes is None:
            return
        json_node = parse_uiautomator_node(node)
        json_node['id'] = str(uuid.uuid4())
        if node.childNodes:
            children = []
            for n in node.childNodes:
                sub_hierarchy = travel(n)
                if sub_hierarchy:
                    children.append(sub_hierarchy)
            json_node['children'] = children
        return json_node

    return travel(root)


def get_ios_hierarchy(d, scale):
    sourcejson = d.source(format='json')

    def travel(node):
        node['id'] = str(uuid.uuid4())
        if node.get('rect'):
            rect = node['rect']
            nrect = {}
            for k, v in rect.items():
                nrect[k] = v * scale
            node['rect'] = nrect

        for child in node.get('children', []):
            travel(child)
        return node

    return travel(sourcejson)

if __name__ == '__main__':
    pass

