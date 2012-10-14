#!/usr/bin/env monkeyrunner
# Devices manager.
# Manage devices connection and devices control.
# Provide devices connection PnP feature, too.
# Author : SeongJae Park <sj38.park@gmail.com>
# License : GPLv3

import os
import socket
import threading
import time

from com.android.monkeyrunner import MonkeyRunner, MonkeyDevice, MonkeyImage

import log

TYPE_ANDROID = "android"
TYPE_PC = "pc"
CONNECT_FAIL = "Fail to connect"
FOCUS_FAIL = "Fail to focus"

MONK_CONN_TIMEOUT = 10

# device is list of type, id, name, connections, focused, resolution.
# type is "android" or "pc"
# id is address for device. ip or serial #.
# name is product name or PC host name.
# connections is connections for device control.
# If PC, just one socket to pc_controller.
# If Android, list of MonkeyDevice and AGI connected socket.
# focused is whether this device will be controlled.
# resolution is screen resolution

_devices = []
_stop_device_lookup_thread = False

def devices():
    f = os.popen("adb devices")
    results = f.readlines()
    f.close()
    parsed = []
    for result in results[1:-1]:
        devid = result.split()[0]
        f = os.popen("adb -s %s shell getprop ro.product.model" % devid)
        name = f.readlines()[0][0:-1]
        f.close()

        parsed.append("%s\t%s\t%s" % (TYPE_ANDROID, devid, name))
    #TODO: See PCs.
    return parsed

def connected_devices():
    results = []
    for device in _devices:
        results.append("%s %s %s %s, %s, %s" % (
            device[0], device[1], device[2],
            device[3],device[4], device[5]))
    return results

def _convert_arg(arg, type_, range_):
    if isinstance(arg, type_):
        return arg
    try:
        arg = type_(arg)
    except:
        return "argument is not %s" % type_
    if range_ and (arg < range_[0] or arg > range_[1]):
        return "argument is not in range of %d, %d" % (range_[0], range_[1])
    return arg

def connect(nth):
    devices_ = devices()
    nth = _convert_arg(nth, int, (0, len(devices_) - 1))
    if not isinstance(nth, int):
        return "%s : %s" % (CONNECT_FAIL, nth)

    dev_base_info = devices_[nth].split()
    devid = dev_base_info[1]
    for i in range(len(_devices)):
        device = _devices[i]
        if device[1] == devid:
            del _devices[i]
            _devices.append(device)
            return

    name = " ".join(dev_base_info[2:])
    mdev = MonkeyRunner.waitForConnection(MONK_CONN_TIMEOUT, devid)
    #TODO: Do agi work
    agiconn = None
    focused = False
    resolution = [mdev.getProperty("display.width"),
            mdev.getProperty("display.height")]
    _devices.append([TYPE_ANDROID, devid, name,
            [mdev, agiconn], focused, resolution])

# focus with no argument is same as clear focus.
def focus(*nths):
    will_focuses = []
    for nth in nths:
        nth = _convert_arg(nth, int, (0, len(_devices) - 1))
        if not isinstance(nth, int):
            return "%s : %s" % (FOCUS_FAIL, nth)

        will_focuses.append(nth)
    for device in _devices:
        device[4] = False
    for i in will_focuses:
        _devices[i][4] = True

def _control_android(collect_result, lambda_, *args):
    results = []
    for dev in _devices:
        if dev[0] != TYPE_ANDROID:
            continue
        if dev[4]:
            results.append(lambda_(dev[3][0], args))
    if collect_result:
        return results

def drag(x1, y1, x2, y2, duration=0.1, steps=10):
    x1 = _convert_arg(x1, int, None)
    y1 = _convert_arg(y1, int, None)
    x2 = _convert_arg(x2, int, None)
    y2 = _convert_arg(y2, int, None)
    duration = _convert_arg(duration, float, None)
    steps = _convert_arg(steps, int, None)
    _control_android(False,
            lambda x,y: x.drag((y[0], y[1]), (y[2], y[3]), y[4], y[5]),
            x1, y1, x2, y2, duration, steps)

def get_property(key):
    return _control_android(True,
            lambda x,y: x.getProperty(y[0]),
            key)

def get_system_property(key):
    return _control_android(True,
            lambda x,y: x.getSystemProperty(y[0]),
            key)

def install_package(path):
    _control_android(False, lambda x,y: x.installPackage(y[0]), path)

def press(type_, name):
    name = "KEYCODE_%s" % name
    type_ = eval("MonkeyDevice.%s" % type_)
    _control_android(False, lambda x,y: x.press(y[0], y[1]), name, type_)

def reboot(bootload_type):
    _control_android(False, lambda x,y: x.reboot(y[0]), bootload_type)

def remove_package(package):
    _control_android(False, lambda x,y: x.remove_package(y[0]), package)

def shell(*cmd):
    cmd = " ".join(cmd)
    return _control_android(True, lambda x,y: x.shell(y[0]), cmd)

def take_snapshot(path=None):
    if not path:
        now = time.localtime()
        path = "ash_snapshot_%04d-%02d-%02d-%02d-%02d-%02d" % (
                now.tm_year, now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec)
    results = _control_android(True, lambda x,y: x.takeSnapshot())
    for i in range(len(results)):
        result = results[i]
        result.writeToFile("%s_%d" % (path, i), "png")

def touch(type_, x, y):
    x = _convert_arg(x, int, None)
    y = _convert_arg(y, int, None)
    type_ = eval("MonkeyDevice.%s" % type_)
    _control_android(False, lambda x,y: x.touch(y[0], y[1], y[2]), x, y, type_)

def wake():
    _control_android(False, lambda x,y: x.wake())

# Device connection lookup thread.
class _DeviceLookupThread(threading.Thread):
    def run(self):
        while True:
            if _stop_device_lookup_thread: break
            #TODO: get current physically connected device, connect logically.
