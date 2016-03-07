#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
brick-logger
Copyright (C) 2015 Matthias Bolte <matthias@tinkerforge.com>
Copyright (C) 2012, 2014 Roland Dudko <roland.dudko@gmail.com>
Copyright (C) 2012, 2014 Marvin Lutz <marvin.lutz.mail@gmail.com>

Commandline data logger tool for Bricklets and Bricks

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public
License along with this program; if not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

data_logger_version = '2.0.2'
merged_data_logger_modules = True


import csv  # CSV_Writer
from datetime import datetime  # CSV_Data
import os  # CSV_Writer
from shutil import copyfile
import sys  # CSV_Writer
from threading import Timer
import time  # Writer Thread
import math
import locale

if 'merged_data_logger_modules' not in globals():
    from brickv.data_logger.event_logger import EventLogger

def utf8_strftime(timestamp, fmt):
    encoding = locale.getlocale()[1]

    # FIXME: Mac OS X doesn't have LANG set when running from an .app container.
    # therefore, locale.setlocale() cannot detect the encoding from the environment.
    # in this case we just default to UTF-8 and hope for the best
    if encoding == None:
        encoding = 'utf-8'

    return datetime.fromtimestamp(timestamp).strftime(fmt).decode(encoding).encode('utf-8')

def timestamp_to_de(timestamp):
    return utf8_strftime(timestamp, '%d.%m.%Y %H:%M:%S')

def timestamp_to_de_msec(timestamp):
    return timestamp_to_de(timestamp) + ',' + ('%.3f' % math.modf(timestamp)[0])[2:]

def timestamp_to_us(timestamp):
    return utf8_strftime(timestamp, '%m/%d/%Y %H:%M:%S')

def timestamp_to_us_msec(timestamp):
    return timestamp_to_us(timestamp) + '.' + ('%.3f' % math.modf(timestamp)[0])[2:]

def timestamp_to_iso(timestamp, milli=False):
    """
    Format a timestamp in ISO 8601 standard
    ISO 8601 = YYYY-MM-DDThh:mm:ss.fff+tz:tz
               2014-09-10T14:12:05.563+02:00
    """

    if time.localtime().tm_isdst and time.daylight:
        offset = -time.altzone / 60
    else:
        offset = -time.timezone / 60

    tz = '%02d:%02d' % (abs(offset) / 60, abs(offset) % 60)

    if offset < 0:
        tz = '-' + tz
    else:
        tz = '+' + tz

    if milli:
        ms = '.' + ('%.3f' % math.modf(timestamp)[0])[2:]
    else:
        ms = ''

    return utf8_strftime(timestamp, '%Y-%m-%dT%H:%M:%S') + ms + tz

def timestamp_to_iso_msec(timestamp):
    return timestamp_to_iso(timestamp, True)

def timestamp_to_unix(timestamp):
    return str(int(timestamp))

def timestamp_to_unix_msec(timestamp):
    return '%.3f' % timestamp

def timestamp_to_strftime(timestamp, time_format):
    try:
        return utf8_strftime(timestamp, time_format.encode('utf-8'))
    except Exception as e:
        return 'Error: ' + str(e).replace('\n', ' ')

class DataLoggerException(Exception):
    # Error Codes
    DL_MISSING_ARGUMENT = -1  # Missing Arguments in Config File
    DL_FAILED_VALIDATION = -2  # Validation found errors in the configuration file
    DL_CRITICAL_ERROR = -42  # For all other critical errors

    def __init__(self, err_code=DL_CRITICAL_ERROR, desc="No Description!"):
        self.value = err_code
        self.description = desc

    def __str__(self):
        return str("ERROR[DL" + str(self.value) + "]: " + str(self.description))


'''
/*---------------------------------------------------------------------------
                                CSVData
 ---------------------------------------------------------------------------*/
 '''


class CSVData(object):
    """
    This class is used as a temporary save spot for all csv relevant data.
    """

    def __init__(self, timestamp, name, uid, var_name, raw_data, var_unit):
        """
        timestamp -- time data was
        name      -- display name of Brick(let)
        uid       -- UID of Brick(let)
        var_name  -- name of logged value
        raw_data  -- logged value
        var_unit  -- unit of logged value
        """
        self.timestamp = timestamp # datatime object
        self.name = name
        self.uid = uid
        self.var_name = var_name
        self.raw_data = raw_data
        self.var_unit = var_unit

    def __str__(self):
        """
        Simple Debug function for easier display of the object.
        """
        return "[TIME=" + str(self.timestamp) + \
               ";NAME=" + str(self.name) + \
               ";UID=" + str(self.uid) + \
               ";VAR=" + str(self.var_name) + \
               ";RAW=" + str(self.raw_data) + \
               ";UNIT=" + str(self.var_unit) + "]"

'''
/*---------------------------------------------------------------------------
                                LoggerTimer
 ---------------------------------------------------------------------------*/
 '''


class LoggerTimer(object):
    """This class provides a timer with a repeat functionality based on a interval"""

    def __init__(self, interval, func_name, var_name, device):
        """
        interval -- the repeat interval in seconds
        func -- the function which will be called
        """
        self.exit_flag = False
        if interval < 0:
            interval = 0

        self._interval = interval # in seconds
        self._func_name = func_name
        self._var_name = var_name
        self._device = device
        self._was_started = False
        self._t = Timer(self._interval, self._loop)

    def _loop(self):
        """Runs the <self._func_name> function every <self._interval> seconds"""
        start = time.time() # FIXME: use time.monotonic() in Python 3
        getattr(self._device, self._func_name)(self._var_name)
        elapsed = max(time.time() - start, 0) # FIXME: use time.monotonic() in Python 3
        self.cancel()
        if self.exit_flag:
            return
        self._t = Timer(max(self._interval - elapsed, 0), self._loop)
        self.start()

    def start(self):
        """Starts the timer if <self._interval> is not 0 otherwise the
           timer will be canceled
        """
        if self._interval == 0:
            self.cancel()
            return

        self._t.start()
        self._was_started = True

    def stop(self):
        self.exit_flag = True
        self._was_started = False

    def cancel(self):
        self._t.cancel()

    def join(self):
        if self._interval == 0:  # quick fix for no timer.start()
            return

        if self._was_started:
            self._t.join()


"""
/*---------------------------------------------------------------------------
                                Utilities
 ---------------------------------------------------------------------------*/
"""


class Utilities(object):
    """
    This class provides some utility functions for the data logger project
    """

    def parse_to_int(string):
        """
        Returns an integer out of a string.
        0(Zero) -- if string is negative or an exception raised during the converting process.
        """
        try:
            ret = int(float(string))
            if ret < 0:
                ret = 0
            return ret
        except ValueError:
            # EventLogger.debug("DataLogger.parse_to_int(" + string + ") could not be parsed! Return 0 for the Timer.")
            return 0

    parse_to_int = staticmethod(parse_to_int)

    def parse_to_bool(bool_string):
        """
        Returns a 'True', if the string is equals to 'true' or 'True'.
        Otherwise it'll return a False
        """
        if bool_string == "true" or bool_string == "True" or bool_string == "TRUE":
            return True
        else:
            return False

    parse_to_bool = staticmethod(parse_to_bool)

    def parse_device_name(device_name):
        tmp = device_name.split("[")
        if len(tmp) == 1:
            return tmp[0], None

        device = tmp[0][:len(tmp[0]) - 1]
        uid = tmp[1][:len(tmp[1]) - 1]

        return device, uid

    parse_device_name = staticmethod(parse_device_name)

    def replace_right(source, target, replacement, replacements=None):
        return replacement.join(source.rsplit(target, replacements))

    replace_right = staticmethod(replace_right)

    def check_file_path_exists(file_path):
        try:
            dir_path = os.path.dirname(file_path)
            if dir_path == "" or dir_path is None:
                if file_path == "" or file_path is None:
                    # no filename - dir
                    return False
                else:
                    # filename - but no dir
                    return True
            elif os.path.isdir(dir_path):
                # dir found
                return True
            return False
        except Exception:
            return False

    check_file_path_exists = staticmethod(check_file_path_exists)

    def is_valid_string(string_value, min_length=0):
        """
        Returns True if 'string_value' is of type basestring and has at least a size of
        'min_length'
        """
        if not isinstance(string_value, basestring) or len(string_value) < min_length:
            return False
        return True

    is_valid_string = staticmethod(is_valid_string)


'''
/*---------------------------------------------------------------------------
                                CSVWriter
 ---------------------------------------------------------------------------*/
 '''


class CSVWriter(object):
    """
    This class provides the actual open/write functions, which are used by the CSVWriterJob class to write logged data into
    a CSV formatted file.
    """

    def __init__(self, file_path, max_file_count=1, max_file_size=0):
        """
        file_path = Path to the csv file
        """
        self._file_path = file_path
        # check if file path exists
        if not Utilities.check_file_path_exists(self._file_path):
            raise Exception("File Path not found! -> " + str(self._file_path))

        self._raw_file = None
        self._csv_file = None

        if max_file_size < 0:
            max_file_size = 0
        self._file_size = max_file_size

        # HINT: create always at least 1 backup file!
        if max_file_count < 1:
            max_file_count = 1

        self._file_count = max_file_count

        self._open_file_A()

    def _open_file_A(self):
        """Opens a file in append mode."""

        # newline problem solved + import sys
        if sys.version_info >= (3, 0, 0):
            self._raw_file = open(self._file_path, 'a', newline='')  # FIXME append or write?!
        else:
            self._raw_file = open(self._file_path, 'ab')

        self._csv_file = csv.writer(self._raw_file, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # if the file is empty, create a csv header
        if self._file_is_empty():
            self._write_header()

    def _file_is_empty(self):
        """
        Simple check if the file is empty.
        Return:
            True  - File is empty or missing
            False - File is not empty
        """
        try:
            if os.stat(self._file_path).st_size > 0:
                return False
            else:
                return True
        except OSError:
            return True

    def _write_header(self):
        """Writes a csv header into the file"""
        if not self._file_is_empty():
            EventLogger.debug("File is not empty")
            return

        EventLogger.debug("CSVWriter._write_header() - done")
        self._csv_file.writerow(["TIME"] + ["NAME"] + ["UID"] + ["VAR"] + ["RAW"] + ["UNIT"])
        self._raw_file.flush()

    def write_data_row(self, csv_data):
        """
        Write a row into the csv file.
        Return:
            True  - Row was written into thee file
            False - Row was not written into the File
        """
        if self._raw_file is None or self._csv_file is None:
            return False

        self._csv_file.writerow([csv_data.timestamp] + [csv_data.name] + [csv_data.uid] + [csv_data.var_name] + [str(csv_data.raw_data)] + [csv_data.var_unit])
        self._raw_file.flush()

        if self._file_size > 0:
            self._rolling_file()

        return True

    def set_file_path(self, new_file_path):
        """
        Sets a new file path.
        Return:
            True  - File path was updated and successfully opened
            False - File path could not be updated or opened
        """
        if not self.close_file():
            return False

        self._file_path = new_file_path
        self._open_file_A()
        return True

    def reopen_file(self):
        """
        Tries to reopen a file, if the file was manually closed.
        Return:
            True  - File could be reopened
            False - File could not be reopened
        """
        if self._raw_file is not None and self._csv_file is not None:
            return False

        self._open_file_A()
        return True

    def close_file(self):
        """
        Tries to close the current file.
        Return:
            True  - File was close
            False - File could not be closed
        """
        if self._raw_file is None or self._csv_file is None:
            return False
        try:
            self._raw_file.close()
            self._csv_file = None
            self._raw_file = None
            return True

        except ValueError:
            return False

    def _rolling_file(self):
        f_size = os.path.getsize(self._file_path)
        if f_size > self._file_size:
            # self.set_file_path(self._create_new_file_name(self._file_path))
            EventLogger.info(
                "Max Filesize(" + "%.3f" % (self._file_size / 1024.0 / 1024.0) + " MB) reached! Rolling Files...")
            self._roll_files()

    # FIXME: only files with a . are working!
    def _roll_files(self):
        i = self._file_count

        self.close_file()

        while True:
            if i == 0:
                # first file reached
                break

            tmp_file_name = Utilities.replace_right(self._file_path, ".", "(" + str(i) + ").", 1)

            if os.path.exists(tmp_file_name):
                if i == self._file_count:
                    # max file count -> delete
                    os.remove(tmp_file_name)
                    EventLogger.debug("Rolling Files... removed File(" + str(i) + ")")

                else:
                    # copy file and remove old
                    copyfile(tmp_file_name, Utilities.replace_right(self._file_path, ".", "(" + str(i + 1) + ").", 1))
                    EventLogger.debug("Rolling Files... copied File(" + str(i) + ") into (" + str(i + 1) + ")")
                    os.remove(tmp_file_name)

            i -= 1

        if self._file_count != 0:
            copyfile(self._file_path, Utilities.replace_right(self._file_path, ".", "(" + str(1) + ").", 1))
            EventLogger.debug("Rolling Files... copied original File into File(1)")
        os.remove(self._file_path)
        self._open_file_A()



import json

if 'merged_data_logger_modules' not in globals():
    from brickv.bindings.ip_connection import base58decode
    from brickv.data_logger.event_logger import EventLogger
    from brickv.data_logger.utils import DataLoggerException, Utilities
    from brickv.data_logger.loggable_devices import device_specs
else:
    from tinkerforge.ip_connection import base58decode

def fix_strings(obj):
    if isinstance(obj, unicode):
        return obj.encode('utf-8')
    elif isinstance(obj, dict):
        fixed_obj = {}

        for key in obj:
            fixed_obj[fix_strings(key)] = fix_strings(obj[key])

        return fixed_obj
    elif isinstance(obj, list):
        return [fix_strings(item) for item in obj]
    else:
        return obj

def load_and_validate_config(filename):
    EventLogger.info('Loading config from file: {0}'.format(filename))

    try:
        with open(filename, 'rb') as f:
            s = f.read()

        config = json.loads(s, encoding='utf-8')
    except Exception as e:
        EventLogger.critical('Could not parse config file as JSON: {0}'.format(e))
        return None

    config = fix_strings(config)

    if not ConfigValidator(config).validate():
        return None

    EventLogger.info('Config successfully loaded from: {0}'.format(filename))

    return config

def save_config(config, filename):
    EventLogger.info('Saving config to file: {0}'.format(filename))

    try:
        s = json.dumps(config, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')

        with open(filename, 'wb') as f:
            f.write(s)
    except Exception as e:
        EventLogger.critical('Could not write config file as JSON: {0}'.format(e))
        return False

    EventLogger.info('Config successfully saved to: {0}'.format(filename))

    return True

""""
/*---------------------------------------------------------------------------
                                ConfigValidator
 ---------------------------------------------------------------------------*/
"""


class ConfigValidator(object):
    """
    This class validates the (JSON) config file
    """
    MIN_INTERVAL = 0

    def __init__(self, config):
        self._error_count = 0
        self._config = config

        # FIXME: dont access the config before its validated. also this code should not be here
        # but somewhere else. it has nothing to do with validation
        #file_count = self._config['data']['csv']['file_count']
        #file_size = self._config['data']['csv']['file_size']
        #self._log_space_counter = LogSpaceCounter(file_count, file_size)

    def _report_error(self, message):
        self._error_count += 1
        EventLogger.critical(message)

    def validate(self):
        """
        This function performs the validation of the various sections of the JSON
        configuration file
        """
        EventLogger.info("Validating config file")

        self._validate_hosts()
        self._validate_data()
        self._validate_debug()
        self._validate_devices()

        if self._error_count > 0:
            EventLogger.critical("Validation found {0} errors".format(self._error_count))
        else:
            EventLogger.info("Validation successful")

        #logging_time = self._log_space_counter.calculate_time()
        #if self._log_space_counter.file_size != 0:
        #    EventLogger.info("Logging time until old data will be overwritten.")
        #    EventLogger.info("Days: " + str(logging_time[0]) +
        #                     " Hours: " + str(logging_time[1]) +
        #                     " Minutes: " + str(logging_time[2]) +
        #                     " Seconds: " + str(logging_time[3]))
        #EventLogger.info("Will write about " + str(
        #    int(self._log_space_counter.lines_per_second + 0.5)) + " lines per second into the log-file.")

        return self._error_count == 0

    def _validate_hosts(self):
        try:
            hosts = self._config['hosts']
        except KeyError:
            self._report_error('Config has no "hosts" section')
            return

        if not isinstance(hosts, dict):
            self._report_error('"hosts" section is not a dict')
            return

        try:
            hosts['default']
        except KeyError:
            self._report_error('Config has no default host')

        for host_id, host in hosts.items():
            # name
            try:
                name = host['name']
            except KeyError:
                self._report_error('Host "{0}" has no name'.format(host_id))
            else:
                if not isinstance(name, basestring):
                    self._report_error('Name of host "{0}" is not a string'.format(host_id))
                elif len(name) == 0:
                    self._report_error('Name of host "{0}" is empty'.format(host_id))

            # port
            try:
                port = host['port']
            except KeyError:
                self._report_error('Host "{0}" has no port'.format(host_id))
            else:
                if not isinstance(port, int):
                    self._report_error('Port of host "{0}" is not an int'.format(host_id))
                elif port < 1 or port > 65535:
                    self._report_error('Port of host "{0}" is out-of-range'.format(host_id))

    def _validate_data(self):
        try:
            data = self._config['data']
        except KeyError:
            self._report_error('Config has no "data" section')
            return

        # time_format
        try:
            time_format = data['time_format']
        except KeyError:
            self._report_error('"data" section has no "time_format" member')
        else:
            if not isinstance(time_format, basestring):
                self._report_error('"data/time_format" is not a string')
            elif time_format not in ['de', 'de-msec', 'us', 'us-msec', 'iso', 'iso-msec', 'unix', 'unix-msec', 'strftime']:
                self._report_error('Invalid "data/time_format" value: {0}'.format(time_format))

        # time_format_strftime (optional)
        try:
            time_format_strftime = data['time_format_strftime']
        except KeyError:
            data['time_format_strftime'] = '%Y%m%d_%H%M%S'
        else:
            if not isinstance(time_format_strftime, basestring):
                self._report_error('"data/time_format_strftime" is not a string')

        self._validate_data_csv()

    def _validate_data_csv(self):
        try:
            csv = self._config['data']['csv']
        except KeyError:
            self._report_error('Config has no "data/csv" section')
            return

        # enabled
        try:
            enabled = csv['enabled']
        except KeyError:
            self._report_error('"data/csv" section has no "enabled" member')
        else:
            if not isinstance(enabled, bool):
                self._report_error('"data/csv/enabled" is not an bool')

        # file_name
        try:
            file_name = csv['file_name']
        except KeyError:
            self._report_error('"data/csv" section has no "file_name" member')
        else:
            if not isinstance(file_name, basestring):
                self._report_error('"data/csv/file_name" is not an string')
            elif len(file_name) == 0:
                self._report_error('"data/csv/file_name" is empty')

    def _validate_debug(self):
        try:
            debug = self._config['debug']
        except KeyError:
            self._report_error('Config has no "debug" section')
            return

        # time_format
        try:
            time_format = debug['time_format']
        except KeyError:
            self._report_error('"debug" section has no "time_format" member')
        else:
            if not isinstance(time_format, basestring):
                self._report_error('"debug/time_format" is not a string')
            elif time_format not in ['de', 'us', 'iso', 'unix']:
                self._report_error('Invalid "debug/time_format" value: {0}'.format(time_format))

        self._validate_debug_log()

    def _validate_debug_log(self):
        try:
            log = self._config['debug']['log']
        except KeyError:
            self._report_error('Config has no "debug/log" section')
            return

        # enabled
        try:
            enabled = log['enabled']
        except KeyError:
            self._report_error('"debug/log" section has no "enabled" member')
        else:
            if not isinstance(enabled, bool):
                self._report_error('"debug/log/enabled" is not an bool')

        # file_name
        try:
            file_name = log['file_name']
        except KeyError:
            self._report_error('"debug/log" section has no "file_name" member')
        else:
            if not isinstance(file_name, basestring):
                self._report_error('"debug/log/file_name" is not an string')
            elif len(file_name) == 0:
                self._report_error('"debug/log/file_name" is empty')

        # level
        try:
            level = log['level']
        except KeyError:
            self._report_error('"debug/log" section has no "level" member')
        else:
            if not isinstance(level, basestring):
                self._report_error('"debug/log/level" is not an integer')
            elif level not in ['debug', 'info', 'warning', 'error', 'critical']:
                self._report_error('Invalid "debug/log/level" value: {0}'.format(level))

    def _validate_devices(self):
        try:
            devices = self._config['devices']
        except KeyError:
            self._report_error('Config has no "devices" section')
            return

        if not isinstance(devices, list):
            self._report_error('"devices" section is not a list')
            return

        for device in devices:
            # uid
            try:
                uid = device['uid']
            except KeyError:
                self._report_error('Device has no UID')
                continue

            if not isinstance(uid, basestring):
                self._report_error('Device UID is not a string')
                continue

            if len(uid) > 0:
                try:
                    decoded_uid = base58decode(uid)
                except Exception as e:
                    self._report_error('Invalid device UID: {0}'.format(uid))
                    continue

                if decoded_uid < 1 or decoded_uid > 0xFFFFFFFF:
                    self._report_error('Device UID is out-of-range: {0}'.format(uid))
                    continue

            # name
            try:
                name = device['name']
            except KeyError:
                self._report_error('Device "{0}" has no name'.format(uid))
                continue

            if not isinstance(name, basestring):
                self._report_error('Name of device "{0}" is not a string'.format(uid))
                continue
            elif len(name) == 0:
                self._report_error('Device "{0}" has empty name'.format(uid))
                continue
            elif name not in device_specs:
                self._report_error('Device "{0}" has unknwon name: {1}'.format(uid, name))
                continue

            device_spec = device_specs[name]

            # host
            try:
                host = device['host']
            except KeyError:
                self._report_error('Device "{0}" has no host'.format(uid))
            else:
                if not isinstance(host, basestring):
                    self._report_error('Host of device "{0}" is not a string'.format(uid))
                elif len(host) == 0:
                    self._report_error('Host of device "{0}" is empty'.format(uid))
                elif host not in self._config['hosts']:
                    self._report_error('Host of device "{0}" is unknown: {1}'.format(uid, host))

            # values
            try:
                values = device['values']
            except KeyError:
                self._report_error('Device "{0}" has no values'.format(uid))
            else:
                if not isinstance(values, dict):
                    self._report_error('"values" of device "{0}" is not a dict'.format(uid))
                elif len(values) == 0:
                    self._report_error('"values" of device "{0}" is empty'.format(uid))
                else:
                    for value_spec in device_spec['values']:
                        try:
                            value = values[value_spec['name']]
                        except KeyError:
                            self._report_error('Value "{0}" of device "{1}" is missing'.format(value_spec['name'], uid))
                            continue

                        # interval
                        try:
                            interval = value['interval']
                        except KeyError:
                            self._report_error('Value "{0}" of device "{1}" has no interval'.format(value_spec['name'], uid))
                        else:
                            if not isinstance(interval, int) and not isinstance(interval, float):
                                self._report_error('Interval of value "{0}" of device "{1}" is neiter an int nor a float'.format(value_spec['name'], uid))
                            elif interval < 0:
                                self._report_error('Interval of value "{0}" of device "{1}" is ouf-of-range'.format(value_spec['name'], uid))

                        # subvalues
                        if value_spec['subvalues'] != None:
                            try:
                                subvalues = value['subvalues']
                            except KeyError:
                                self._report_error('Value "{0}" of device "{1}" has no subvalues'.format(value_spec['name'], uid))
                            else:
                                if not isinstance(subvalues, dict):
                                    self._report_error('Subvalues of value "{0}" of device "{1}" is not a dict'.format(value_spec['name'], uid))
                                else:
                                    for subvalue_spec_name in value_spec['subvalues']:
                                        try:
                                            subvalue_value = subvalues[subvalue_spec_name]
                                        except:
                                            self._report_error('Subvalue "{0}" of value "{1}" of device "{2}" is missing'
                                                               .format(subvalue_spec_name, value_spec['name'], uid))
                                            continue

                                        if not isinstance(subvalue_value, bool):
                                            self._report_error('Subvalue "{0}" of value "{1}" of device "{2}" is not a bool'
                                                               .format(subvalue_spec_name, value_spec['name'], uid))

            # options
            if device_spec['options'] != None:
                try:
                    options = device['options']
                except KeyError:
                    self._report_error('Device "{0}" has no options'.format(uid))
                else:
                    if not isinstance(options, dict):
                        self._report_error('"options" of device "{0}" is not a dict'.format(uid))
                    elif len(options) == 0:
                        self._report_error('"options" of device "{0}" is empty'.format(uid))
                    else:
                        for option_spec in device_spec['options']:
                            try:
                                option = options[option_spec['name']]
                            except KeyError:
                                self._report_error('Option "{0}" of device "{1}" is missing'.format(option_spec['name'], uid))
                                continue

                            # value
                            try:
                                value = option['value']
                            except KeyError:
                                self._report_error('Option "{0}" of device "{1}" has no interval'.format(option_spec['name'], uid))
                            else:
                                valid = False

                                if option_spec['type'] == 'choice':
                                    if not isinstance(value, basestring):
                                        self._report_error('Value of option "{0}" of device "{1}" is not a string'
                                                           .format(option_spec['name'], uid))
                                        continue

                                    for option_value_spec in option_spec['values']:
                                        if option_value_spec[0] == value:
                                            valid = True
                                            break
                                elif option_spec['type'] == 'int':
                                    if not isinstance(value, int):
                                        self._report_error('Value of option "{0}" of device "{1}" is not an int'
                                                           .format(option_spec['name'], uid))
                                        continue

                                    valid = value >= option_spec['minimum'] and value <= option_spec['maximum']
                                elif option_spec['type'] == 'bool':
                                    if not isinstance(value, bool):
                                        self._report_error('Value of option "{0}" of device "{1}" is not a bool'
                                                           .format(option_spec['name'], uid))
                                        continue

                                    valid = True

                                if not valid:
                                    self._report_error('Value of option "{0}" of device "{1}" is invalid: {2}'
                                                       .format(option_spec['name'], uid, value))

        #if interval > 0:
        #    self._log_space_counter.add_lines_per_second(interval * logged_values)


""""
/*---------------------------------------------------------------------------
                                LogSpaceCounter
 ---------------------------------------------------------------------------*/
"""


class LogSpaceCounter(object):
    """
    This class provides functions to count the average lines per second
    which will be written into the log file
    """

    def __init__(self, file_count, file_size):
        """
        file_count -- the amount of logfiles
        file_size -- the size of each file
        """
        self.file_count = file_count
        self.file_size = file_size

        self.lines_per_second = 0.0

    def add_lines_per_second(self, lines):
        self.lines_per_second += lines

    def calculate_time(self):
        """
        This function calculates the time where the logger can
        save data without overwriting old ones.

        18k lines -> 1MB
        """
        if self.lines_per_second <= 0 or self.file_size == 0:
            return 0, 0, 0, 0

        max_available_space = (self.file_count + 1) * ((self.file_size / 1024.0) / 1024.0)
        seconds_for_one_MB = 18000.0 / self.lines_per_second

        sec = seconds_for_one_MB * max_available_space * 1.0

        days = int(sec / 86400.0)
        sec -= 86400.0 * days

        hrs = int(sec / 3600.0)
        sec -= 3600.0 * hrs

        mins = int(sec / 60.0)
        sec -= 60.0 * mins

        return days, hrs, mins, int(sec)



import time

if 'merged_data_logger_modules' not in globals():
    from brickv.bindings.bricklet_accelerometer import BrickletAccelerometer
    from brickv.bindings.bricklet_ambient_light import BrickletAmbientLight
    from brickv.bindings.bricklet_ambient_light_v2 import BrickletAmbientLightV2
    from brickv.bindings.bricklet_analog_in import BrickletAnalogIn
    from brickv.bindings.bricklet_analog_in_v2 import BrickletAnalogInV2
    from brickv.bindings.bricklet_analog_out_v2 import BrickletAnalogOutV2
    from brickv.bindings.bricklet_barometer import BrickletBarometer
    from brickv.bindings.bricklet_color import BrickletColor
    from brickv.bindings.bricklet_current12 import BrickletCurrent12
    from brickv.bindings.bricklet_current25 import BrickletCurrent25
    from brickv.bindings.bricklet_distance_ir import BrickletDistanceIR
    from brickv.bindings.bricklet_distance_us import BrickletDistanceUS
    from brickv.bindings.bricklet_dual_button import BrickletDualButton
    from brickv.bindings.bricklet_dust_detector import BrickletDustDetector
    from brickv.bindings.bricklet_gps import BrickletGPS
    from brickv.bindings.bricklet_hall_effect import BrickletHallEffect
    from brickv.bindings.bricklet_humidity import BrickletHumidity
    from brickv.bindings.bricklet_industrial_digital_in_4 import BrickletIndustrialDigitalIn4
    from brickv.bindings.bricklet_industrial_dual_0_20ma import BrickletIndustrialDual020mA
    from brickv.bindings.bricklet_industrial_dual_analog_in import BrickletIndustrialDualAnalogIn
    from brickv.bindings.bricklet_io16 import BrickletIO16
    from brickv.bindings.bricklet_io4 import BrickletIO4
    from brickv.bindings.bricklet_joystick import BrickletJoystick
    # from brickv.bindings.bricklet_laser_range_finder import BrickletLaserRangeFinder #NYI # config: mode, FIXME: special laser handling
    from brickv.bindings.bricklet_led_strip import BrickletLEDStrip
    from brickv.bindings.bricklet_line import BrickletLine
    from brickv.bindings.bricklet_linear_poti import BrickletLinearPoti
    from brickv.bindings.bricklet_load_cell import BrickletLoadCell
    from brickv.bindings.bricklet_moisture import BrickletMoisture
    from brickv.bindings.bricklet_motion_detector import BrickletMotionDetector
    from brickv.bindings.bricklet_multi_touch import BrickletMultiTouch
    from brickv.bindings.bricklet_ptc import BrickletPTC
    from brickv.bindings.bricklet_rotary_encoder import BrickletRotaryEncoder
    from brickv.bindings.bricklet_rotary_poti import BrickletRotaryPoti
    # from brickv.bindings.bricklet_rs232 import BrickletRS232 #NYI FIXME: has to use read_callback to get all data
    from brickv.bindings.bricklet_sound_intensity import BrickletSoundIntensity
    from brickv.bindings.bricklet_temperature import BrickletTemperature
    from brickv.bindings.bricklet_temperature_ir import BrickletTemperatureIR
    from brickv.bindings.bricklet_tilt import BrickletTilt
    from brickv.bindings.bricklet_voltage import BrickletVoltage
    from brickv.bindings.bricklet_voltage_current import BrickletVoltageCurrent
    from brickv.bindings.brick_dc import BrickDC
    from brickv.bindings.brick_imu import BrickIMU
    from brickv.bindings.brick_imu_v2 import BrickIMUV2
    from brickv.bindings.brick_master import BrickMaster
    from brickv.bindings.brick_servo import BrickServo
    from brickv.bindings.brick_stepper import BrickStepper

    from brickv.data_logger.event_logger import EventLogger
    from brickv.data_logger.utils import LoggerTimer, CSVData, \
                                         timestamp_to_de, timestamp_to_us, \
                                         timestamp_to_iso, timestamp_to_unix, \
                                         timestamp_to_de_msec, timestamp_to_us_msec, \
                                         timestamp_to_iso_msec, timestamp_to_unix_msec, \
                                         timestamp_to_strftime
else:
    from tinkerforge.bricklet_accelerometer import BrickletAccelerometer
    from tinkerforge.bricklet_ambient_light import BrickletAmbientLight
    from tinkerforge.bricklet_ambient_light_v2 import BrickletAmbientLightV2
    from tinkerforge.bricklet_analog_in import BrickletAnalogIn
    from tinkerforge.bricklet_analog_in_v2 import BrickletAnalogInV2
    from tinkerforge.bricklet_analog_out_v2 import BrickletAnalogOutV2
    from tinkerforge.bricklet_barometer import BrickletBarometer
    from tinkerforge.bricklet_color import BrickletColor
    from tinkerforge.bricklet_current12 import BrickletCurrent12
    from tinkerforge.bricklet_current25 import BrickletCurrent25
    from tinkerforge.bricklet_distance_ir import BrickletDistanceIR
    from tinkerforge.bricklet_distance_us import BrickletDistanceUS
    from tinkerforge.bricklet_dual_button import BrickletDualButton
    from tinkerforge.bricklet_dust_detector import BrickletDustDetector
    from tinkerforge.bricklet_gps import BrickletGPS
    from tinkerforge.bricklet_hall_effect import BrickletHallEffect
    from tinkerforge.bricklet_humidity import BrickletHumidity
    from tinkerforge.bricklet_industrial_digital_in_4 import BrickletIndustrialDigitalIn4
    from tinkerforge.bricklet_industrial_dual_0_20ma import BrickletIndustrialDual020mA
    from tinkerforge.bricklet_industrial_dual_analog_in import BrickletIndustrialDualAnalogIn
    from tinkerforge.bricklet_io16 import BrickletIO16
    from tinkerforge.bricklet_io4 import BrickletIO4
    from tinkerforge.bricklet_joystick import BrickletJoystick
    #from tinkerforge.bricklet_laser_range_finder import BrickletLaserRangeFinder #NYI # config: mode, FIXME: special laser handling
    from tinkerforge.bricklet_led_strip import BrickletLEDStrip
    from tinkerforge.bricklet_line import BrickletLine
    from tinkerforge.bricklet_linear_poti import BrickletLinearPoti
    from tinkerforge.bricklet_load_cell import BrickletLoadCell
    from tinkerforge.bricklet_moisture import BrickletMoisture
    from tinkerforge.bricklet_motion_detector import BrickletMotionDetector
    from tinkerforge.bricklet_multi_touch import BrickletMultiTouch
    from tinkerforge.bricklet_ptc import BrickletPTC
    from tinkerforge.bricklet_rotary_encoder import BrickletRotaryEncoder
    from tinkerforge.bricklet_rotary_poti import BrickletRotaryPoti
    #from tinkerforge.bricklet_rs232 import BrickletRS232 #NYI FIXME: has to use read_callback to get all data
    from tinkerforge.bricklet_sound_intensity import BrickletSoundIntensity
    from tinkerforge.bricklet_temperature import BrickletTemperature
    from tinkerforge.bricklet_temperature_ir import BrickletTemperatureIR
    from tinkerforge.bricklet_tilt import BrickletTilt
    from tinkerforge.bricklet_voltage import BrickletVoltage
    from tinkerforge.bricklet_voltage_current import BrickletVoltageCurrent
    from tinkerforge.brick_dc import BrickDC
    from tinkerforge.brick_imu import BrickIMU
    from tinkerforge.brick_imu_v2 import BrickIMUV2
    from tinkerforge.brick_master import BrickMaster
    from tinkerforge.brick_servo import BrickServo
    from tinkerforge.brick_stepper import BrickStepper

def value_to_bits(value, length):
    bits = []

    for i in range(length):
        if (value & (1 << i)) != 0:
            bits.append(1)
        else:
            bits.append(0)

    return bits

# special_* functions are for special Bricks/Bricklets. Some device functions can
# return different values, depending on different situations, e.g. the GPS Bricklet.
# If the GPS Bricklet does not have a fix, then the function will return an Error
# instead of the specified return values.

# BrickletColor
def special_get_get_illuminance(device):
    gain, integration_time = device.get_config()

    if gain == BrickletColor.GAIN_1X:
        gain_factor = 1
    elif gain == BrickletColor.GAIN_4X:
        gain_factor = 4
    elif gain == BrickletColor.GAIN_16X:
        gain_factor = 16
    elif gain == BrickletColor.GAIN_60X:
        gain_factor = 60

    if integration_time == BrickletColor.INTEGRATION_TIME_2MS:
        integration_time_factor = 2.4
    elif integration_time == BrickletColor.INTEGRATION_TIME_24MS:
        integration_time_factor = 24
    elif integration_time == BrickletColor.INTEGRATION_TIME_101MS:
        integration_time_factor = 101
    elif integration_time == BrickletColor.INTEGRATION_TIME_154MS:
        integration_time_factor = 154
    elif integration_time == BrickletColor.INTEGRATION_TIME_700MS:
        integration_time_factor = 700

    illuminance = device.get_illuminance()

    return int(round(illuminance * 700.0 / float(gain_factor) / float(integration_time_factor), 1) * 10)

# BrickletGPS
def special_get_gps_coordinates(device):
    if device.get_status()[0] == BrickletGPS.FIX_NO_FIX:
        raise Exception('No fix')
    else:
        return device.get_coordinates()

def special_get_gps_altitude(device):
    if device.get_status()[0] != BrickletGPS.FIX_3D_FIX:
        raise Exception('No 3D fix')
    else:
        return device.get_altitude()

def special_get_gps_motion(device):
    if device.get_status()[0] == BrickletGPS.FIX_NO_FIX:
        raise Exception('No fix')
    else:
        return device.get_motion()

# BrickletMultiTouch
def special_set_multi_touch_options(device, electrode0, electrode1, electrode2, electrode3,
                                    electrode4, electrode5, electrode6, electrode7,
                                    electrode8, electrode9, electrode10, electrode11,
                                    proximity, electrode_sensitivity):
    electrode_config = 0

    if electrode0:
        electrode_config |= 1 << 0

    if electrode1:
        electrode_config |= 1 << 1

    if electrode2:
        electrode_config |= 1 << 2

    if electrode3:
        electrode_config |= 1 << 3

    if electrode4:
        electrode_config |= 1 << 4

    if electrode5:
        electrode_config |= 1 << 5

    if electrode6:
        electrode_config |= 1 << 6

    if electrode7:
        electrode_config |= 1 << 7

    if electrode8:
        electrode_config |= 1 << 8

    if electrode9:
        electrode_config |= 1 << 9

    if electrode10:
        electrode_config |= 1 << 10

    if electrode11:
        electrode_config |= 1 << 11

    if proximity:
        electrode_config |= 1 << 12

    device.set_electrode_config(electrode_config)
    device.set_electrode_sensitivity(electrode_sensitivity)

# BrickletPTC
def special_get_ptc_resistance(device):
    if not device.is_sensor_connected():
        raise Exception('No sensor')
    else:
        return device.get_resistance()

def special_get_ptc_temperature(device):
    if not device.is_sensor_connected():
        raise Exception('No sensor')
    else:
        return device.get_temperature()

device_specs = {
    BrickletAccelerometer.DEVICE_DISPLAY_NAME: {
        'class': BrickletAccelerometer,
        'values': [
            {
                'name': 'Acceleration',
                'getter': lambda device: device.get_acceleration(),
                'subvalues': ['X', 'Y', 'Z'],
                'unit': ['g/1000', 'g/1000', 'g/1000'],
                'advanced': False
            },
            {
                'name': 'Temperature',
                'getter': lambda device: device.get_temperature(),
                'subvalues': None,
                'unit': '°C',
                'advanced': True
            }
        ],
        'options_setter': lambda device, data_rate, full_scale, filter_bandwidth: device.set_configuration(data_rate, full_scale, filter_bandwidth),
        'options': [
            {
                'name': 'Data Rate',
                'type': 'choice',
                'values': [('Off', BrickletAccelerometer.DATA_RATE_OFF),
                           ('3Hz', BrickletAccelerometer.DATA_RATE_3HZ),
                           ('6Hz', BrickletAccelerometer.DATA_RATE_6HZ),
                           ('12Hz', BrickletAccelerometer.DATA_RATE_12HZ),
                           ('25Hz', BrickletAccelerometer.DATA_RATE_25HZ),
                           ('50Hz', BrickletAccelerometer.DATA_RATE_50HZ),
                           ('100Hz', BrickletAccelerometer.DATA_RATE_100HZ),
                           ('400Hz', BrickletAccelerometer.DATA_RATE_400HZ),
                           ('800Hz', BrickletAccelerometer.DATA_RATE_800HZ),
                           ('1600Hz', BrickletAccelerometer.DATA_RATE_1600HZ)],
                'default': '100Hz'
            },
            {
                'name': 'Full Scale',
                'type': 'choice',
                'values': [('2g', BrickletAccelerometer.FULL_SCALE_2G),
                           ('4g', BrickletAccelerometer.FULL_SCALE_4G),
                           ('6g', BrickletAccelerometer.FULL_SCALE_6G),
                           ('8g', BrickletAccelerometer.FULL_SCALE_8G),
                           ('16g', BrickletAccelerometer.FULL_SCALE_16G)],
                'default': '4g'
            },
            {
                'name': 'Filter Bandwidth',
                'type': 'choice',
                'values': [('800Hz', BrickletAccelerometer.FILTER_BANDWIDTH_800HZ),
                           ('400Hz', BrickletAccelerometer.FILTER_BANDWIDTH_400HZ),
                           ('200Hz', BrickletAccelerometer.FILTER_BANDWIDTH_200HZ),
                           ('50Hz', BrickletAccelerometer.FILTER_BANDWIDTH_50HZ)],
                'default': '200Hz'
            }
        ]
    },
    BrickletAmbientLight.DEVICE_DISPLAY_NAME: {
        'class': BrickletAmbientLight,
        'values': [
            {
                'name': 'Illuminance',
                'getter': lambda device: device.get_illuminance(),
                'subvalues': None,
                'unit': 'lx/10',
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletAmbientLightV2.DEVICE_DISPLAY_NAME: {
        'class': BrickletAmbientLightV2,
        'values': [
            {
                'name': 'Illuminance',
                'getter': lambda device: device.get_illuminance(),
                'subvalues': None,
                'unit': 'lx/100',
                'advanced': False
            }
        ],
        'options_setter': lambda device, illuminance_range, integration_time: device.set_configuration(illuminance_range, integration_time),
        'options': [
            {
                'name': 'Illuminance Range',
                'type': 'choice',
                'values': [('Unlimited', 6), # FIXME: BrickletAmbientLightV2.ILLUMINANCE_RANGE_UNLIMITED
                           ('64000Lux', BrickletAmbientLightV2.ILLUMINANCE_RANGE_64000LUX),
                           ('32000Lux', BrickletAmbientLightV2.ILLUMINANCE_RANGE_32000LUX),
                           ('16000Lux', BrickletAmbientLightV2.ILLUMINANCE_RANGE_16000LUX),
                           ('8000Lux', BrickletAmbientLightV2.ILLUMINANCE_RANGE_8000LUX),
                           ('1300Lux', BrickletAmbientLightV2.ILLUMINANCE_RANGE_1300LUX),
                           ('600Lux', BrickletAmbientLightV2.ILLUMINANCE_RANGE_600LUX)],
                'default': '8000Lux'
            },
            {
                'name': 'Integration Time',
                'type': 'choice',
                'values': [('50ms', BrickletAmbientLightV2.INTEGRATION_TIME_50MS),
                           ('100ms', BrickletAmbientLightV2.INTEGRATION_TIME_100MS),
                           ('150ms', BrickletAmbientLightV2.INTEGRATION_TIME_150MS),
                           ('200ms', BrickletAmbientLightV2.INTEGRATION_TIME_200MS),
                           ('250ms', BrickletAmbientLightV2.INTEGRATION_TIME_350MS),
                           ('300ms', BrickletAmbientLightV2.INTEGRATION_TIME_300MS),
                           ('350ms', BrickletAmbientLightV2.INTEGRATION_TIME_350MS),
                           ('400ms', BrickletAmbientLightV2.INTEGRATION_TIME_400MS)],
                'default': '200ms'
            }
        ]
    },
    BrickletAnalogIn.DEVICE_DISPLAY_NAME: {
        'class': BrickletAnalogIn,
        'values': [
            {
                'name': 'Voltage',
                'getter': lambda device: device.get_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': lambda device, voltage_range, average_length: [device.set_range(voltage_range), device.set_averaging(average_length)],
        'options': [
            {
                'name': 'Voltage Range',
                'type': 'choice',
                'values': [('Automatic', BrickletAnalogIn.RANGE_AUTOMATIC),
                           ('3.30V', BrickletAnalogIn.RANGE_UP_TO_3V),
                           ('6.05V', BrickletAnalogIn.RANGE_UP_TO_6V),
                           ('10.32V', BrickletAnalogIn.RANGE_UP_TO_10V),
                           ('36.30V', BrickletAnalogIn.RANGE_UP_TO_36V),
                           ('45.00V', BrickletAnalogIn.RANGE_UP_TO_45V)],
                'default': 'Automatic'
            },
            {
                'name': 'Average Length',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': None,
                'default': 50
            }
        ]
    },
    BrickletAnalogInV2.DEVICE_DISPLAY_NAME: {
        'class': BrickletAnalogInV2,
        'values': [
            {
                'name': 'Voltage',
                'getter': lambda device: device.get_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': lambda device, moving_average_length: device.set_moving_average(moving_average_length),
        'options': [
            {
                'name': 'Moving Average Length',
                'type': 'int',
                'minimum': 1,
                'maximum': 50,
                'suffix': None,
                'default': 50
            }
        ]
    },
    BrickletAnalogOutV2.DEVICE_DISPLAY_NAME: {
        'class': BrickletAnalogOutV2,
        'values': [
            {
                'name': 'Input Voltage',
                'getter': lambda device: device.get_input_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletBarometer.DEVICE_DISPLAY_NAME: {
        'class': BrickletBarometer,
        'values': [
            {
                'name': 'Air Pressure',
                'getter': lambda device: device.get_air_pressure(),
                'subvalues': None,
                'unit': 'mbar/1000',
                'advanced': False
            },
            {
                'name': 'Altitude',
                'getter': lambda device: device.get_altitude(),
                'subvalues': None,
                'unit': 'cm',
                'advanced': False
            },
            {
                'name': 'Chip Temperature',
                'getter': lambda device: device.get_chip_temperature(),
                'subvalues': None,
                'unit': '°C/100',
                'advanced': False
            }
        ],
        'options_setter': lambda device, reference_air_pressure, moving_average_length_air_pressure, \
                                         average_length_air_pressure, average_length_temperature: \
                          [device.set_reference_air_pressure(reference_air_pressure),
                           device.set_averaging(moving_average_length_air_pressure,
                                                average_length_air_pressure,
                                                average_length_temperature)],
        'options': [
            {
                'name': 'Reference Air Pressure',
                'type': 'int',
                'minimum': 10000,
                'maximum': 1200000,
                'suffix': ' mbar/1000',
                'default': 1013250
            },
            {
                'name': 'Moving Average Length (Air Pressure)',
                'type': 'int',
                'minimum': 0,
                'maximum': 25,
                'suffix': None,
                'default': 25
            },
            {
                'name': 'Average Length (Air Pressure)',
                'type': 'int',
                'minimum': 0,
                'maximum': 10,
                'suffix': None,
                'default': 10
            },
            {
                'name': 'Average Length (Temperature)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': None,
                'default': 10
            }
        ]
    },
    BrickletColor.DEVICE_DISPLAY_NAME: {
        'class': BrickletColor,
        'values': [
            {
                'name': 'Color',
                'getter': lambda device: device.get_color(),
                'subvalues': ['Red', 'Green', 'Blue', 'Clear'],
                'unit': [None, None, None, None],
                'advanced': False
            },
            {
                'name': 'Color Temperature',
                'getter': lambda device: device.get_color_temperature(), # FIXME: saturation handling is missing
                'subvalues': None,
                'unit': 'K',
                'advanced': False
            },
            {
                'name': 'Illuminance',
                'getter': special_get_get_illuminance, # FIXME: saturation handling is missing
                'subvalues': None,
                'unit': 'lx/10',
                'advanced': False
            }
        ],
        'options_setter': lambda device, gain, integration_time: device.set_config(gain, integration_time),
        'options': [
            {
                'name': 'Gain',
                'type': 'choice',
                'values': [('1x', BrickletColor.GAIN_1X),
                           ('4x', BrickletColor.GAIN_4X),
                           ('16x', BrickletColor.GAIN_16X),
                           ('60x', BrickletColor.GAIN_60X)],
                'default': '60x'
            },
            {
                'name': 'Integration Time',
                'type': 'choice',
                'values': [('2.4ms', BrickletColor.INTEGRATION_TIME_2MS),
                           ('24ms', BrickletColor.INTEGRATION_TIME_24MS),
                           ('101ms', BrickletColor.INTEGRATION_TIME_101MS),
                           ('154ms', BrickletColor.INTEGRATION_TIME_154MS),
                           ('700ms', BrickletColor.INTEGRATION_TIME_700MS)],
                'default': '154ms'
            }
        ]
    },
    BrickletCurrent12.DEVICE_DISPLAY_NAME: {
        'class': BrickletCurrent12,
        'values': [
            {
                'name': 'Current',
                'getter': lambda device: device.get_current(),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletCurrent25.DEVICE_DISPLAY_NAME: {
        'class': BrickletCurrent25,
        'values': [
            {
                'name': 'Current',
                'getter': lambda device: device.get_current(),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletDistanceIR.DEVICE_DISPLAY_NAME: {
        'class': BrickletDistanceIR,
        'values': [
            {
                'name': 'Distance',
                'getter': lambda device: device.get_distance(),
                'subvalues': None,
                'unit': 'mm',
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletDistanceUS.DEVICE_DISPLAY_NAME: {
        'class': BrickletDistanceUS,
        'values': [
            {
                'name': 'Distance Value',
                'getter': lambda device: device.get_distance_value(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            }
        ],
        'options_setter': lambda device, moving_average_length: device.set_moving_average(moving_average_length),
        'options': [
            {
                'name': 'Moving Average Length',
                'type': 'int',
                'minimum': 0,
                'maximum': 100,
                'suffix': None,
                'default': 20
            }
        ]
    },
    BrickletDualButton.DEVICE_DISPLAY_NAME: {
        'class': BrickletDualButton,
        'values': [
            {
                'name': 'Button State',
                'getter': lambda device: device.get_button_state(),
                'subvalues': ['Left', 'Right'],
                'unit': [None, None], # FIXME: constants?
                'advanced': False
            },
            {
                'name': 'LED State',
                'getter': lambda device: device.get_led_state(),
                'subvalues': ['Left', 'Right'],
                'unit': [None, None], # FIXME: constants?
                'advanced': False
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletDustDetector.DEVICE_DISPLAY_NAME: {
        'class': BrickletDustDetector,
        'values': [
            {
                'name': 'Dust Density',
                'getter': lambda device: device.get_dust_density(),
                'subvalues': None,
                'unit': 'µg/m³',
                'advanced': False
            }
        ],
        'options_setter': lambda device, moving_average_length: device.set_moving_average(moving_average_length),
        'options': [
            {
                'name': 'Moving Average Length',
                'type': 'int',
                'minimum': 0,
                'maximum': 100,
                'suffix': None,
                'default': 100
            }
        ]
    },
    BrickletGPS.DEVICE_DISPLAY_NAME: {
        'class': BrickletGPS,
        'values': [
            {
                'name': 'Coordinates',
                'getter': special_get_gps_coordinates,
                'subvalues': ['Latitude', 'NS', 'Longitude', 'EW', 'PDOP', 'HDOP', 'VDOP', 'EPE'],
                'unit': ['deg/1000000', None, 'deg/1000000', None, '1/100', '1/100', '1/100', 'cm'],
                'advanced': False
            },
            {
                'name': 'Altitude',
                'getter': special_get_gps_altitude,
                'subvalues': ['Altitude', 'Geoidal Separation'],
                'unit': ['cm', 'cm'],
                'advanced': False
            },
            {
                'name': 'Motion',
                'getter': special_get_gps_motion,
                'subvalues': ['Course', 'Speed'],
                'unit': ['deg/100', '10m/h'],
                'advanced': False
            },
            {
                'name': 'Date Time',
                'getter': lambda device: device.get_date_time(),
                'subvalues': ['Date', 'Time'],
                'unit': ['ddmmyy', 'hhmmss|sss'],
                'advanced': False
            },
            {
                'name': 'Status',
                'getter': lambda device: device.get_status(),
                'subvalues': ['Fix', 'Satellites View', 'Satellites Used'],
                'unit': [None, None, None], # FIXME: fix constants?
                'advanced': False
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletHallEffect.DEVICE_DISPLAY_NAME: {
        'class': BrickletHallEffect,
        'values': [
            {
                'name': 'Value',
                'getter': lambda device: device.get_value(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            },
            {
                'name': 'Edge Count',
                'getter': lambda device: device.get_edge_count(False),
                'subvalues': None,
                'unit': None,
                'advanced': False
            }
        ],
        'options_setter': lambda device, edge_count_type, edge_count_debounce: device.set_edge_count_config(edge_count_type, edge_count_debounce),
        'options': [
            {
                'name': 'Edge Count Type',
                'type': 'choice',
                'values': [('Rising', BrickletHallEffect.EDGE_TYPE_RISING),
                           ('Falling', BrickletHallEffect.EDGE_TYPE_FALLING),
                           ('Both', BrickletHallEffect.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            }
        ]
    },
    BrickletHumidity.DEVICE_DISPLAY_NAME: {
        'class': BrickletHumidity,
        'values': [
            {
                'name': 'Humidity',
                'getter': lambda device: device.get_humidity(),
                'subvalues': None,
                'unit': '%RH/10',
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletIndustrialDigitalIn4.DEVICE_DISPLAY_NAME: {
        'class': BrickletIndustrialDigitalIn4,
        'values': [
            {
                'name': 'Value',
                'getter': lambda device: value_to_bits(device.get_value(), 4),
                'subvalues': ['Pin 0', 'Pin 1', 'Pin 2', 'Pin 3'],
                'unit': [None, None, None, None],
                'advanced': False
            },
            {
                'name': 'Edge Count (Pin 0)',
                'getter': lambda device: device.get_edge_count(0, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            },
            {
                'name': 'Edge Count (Pin 1)',
                'getter': lambda device: device.get_edge_count(1, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            },
            {
                'name': 'Edge Count (Pin 2)',
                'getter': lambda device: device.get_edge_count(2, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            },
            {
                'name': 'Edge Count (Pin 3)',
                'getter': lambda device: device.get_edge_count(3, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': lambda device, edge_count_type_pin0, edge_count_debounce_pin0, \
                                         edge_count_type_pin1, edge_count_debounce_pin1, \
                                         edge_count_type_pin2, edge_count_debounce_pin2, \
                                         edge_count_type_pin3, edge_count_debounce_pin3: \
                          [device.set_edge_count_config(0b0001, edge_count_type_pin0, edge_count_debounce_pin0),
                           device.set_edge_count_config(0b0010, edge_count_type_pin1, edge_count_debounce_pin1),
                           device.set_edge_count_config(0b0100, edge_count_type_pin2, edge_count_debounce_pin2),
                           device.set_edge_count_config(0b1000, edge_count_type_pin3, edge_count_debounce_pin3)],
        'options': [
            {
                'name': 'Edge Count Type (Pin 0)',
                'type': 'choice',
                'values': [('Rising', BrickletIndustrialDigitalIn4.EDGE_TYPE_RISING),
                           ('Falling', BrickletIndustrialDigitalIn4.EDGE_TYPE_FALLING),
                           ('Both', BrickletIndustrialDigitalIn4.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin 0)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            },
            {
                'name': 'Edge Count Type (Pin 1)',
                'type': 'choice',
                'values': [('Rising', BrickletIndustrialDigitalIn4.EDGE_TYPE_RISING),
                           ('Falling', BrickletIndustrialDigitalIn4.EDGE_TYPE_FALLING),
                           ('Both', BrickletIndustrialDigitalIn4.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin 1)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            },
            {
                'name': 'Edge Count Type (Pin 2)',
                'type': 'choice',
                'values': [('Rising', BrickletIndustrialDigitalIn4.EDGE_TYPE_RISING),
                           ('Falling', BrickletIndustrialDigitalIn4.EDGE_TYPE_FALLING),
                           ('Both', BrickletIndustrialDigitalIn4.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin 2)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            },
            {
                'name': 'Edge Count Type (Pin 3)',
                'type': 'choice',
                'values': [('Rising', BrickletIndustrialDigitalIn4.EDGE_TYPE_RISING),
                           ('Falling', BrickletIndustrialDigitalIn4.EDGE_TYPE_FALLING),
                           ('Both', BrickletIndustrialDigitalIn4.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin 3)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            }
        ]
    },
    BrickletIndustrialDual020mA.DEVICE_DISPLAY_NAME: {
        'class': BrickletIndustrialDual020mA,
        'values': [
            {
                'name': 'Current (Sensor 0)',
                'getter': lambda device: device.get_current(0),
                'subvalues': None,
                'unit': 'nA',
                'advanced': False
            },
            {
                'name': 'Current (Sensor 1)',
                'getter': lambda device: device.get_current(1),
                'subvalues': None,
                'unit': 'nA',
                'advanced': False
            }
        ],
        'options_setter': lambda device, sample_rate: device.set_sample_rate(sample_rate),
        'options': [
            {
                'name': 'Sample Rate',
                'type': 'choice',
                'values': [('240 SPS', BrickletIndustrialDual020mA.SAMPLE_RATE_240_SPS),
                           ('60 SPS', BrickletIndustrialDual020mA.SAMPLE_RATE_60_SPS),
                           ('15 SPS', BrickletIndustrialDual020mA.SAMPLE_RATE_15_SPS),
                           ('4 SPS', BrickletIndustrialDual020mA.SAMPLE_RATE_4_SPS)],
                'default': '4 SPS'
            }
        ]
    },
    BrickletIndustrialDualAnalogIn.DEVICE_DISPLAY_NAME: {
        'class': BrickletIndustrialDualAnalogIn,
        'values': [
            {
                'name': 'Voltage (Channel 0)',
                'getter': lambda device: device.get_voltage(0),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'Voltage (Channel 1)',
                'getter': lambda device: device.get_voltage(1),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'ADC Values',
                'getter': lambda device: device.get_adc_values(),
                'subvalues': ['Channel 0', 'Channel 1'],
                'unit': [None, None],
                'advanced': True
            }
        ],
        'options_setter': lambda device, sample_rate: device.set_sample_rate(sample_rate),
        'options': [
            {
                'name': 'Sample Rate',
                'type': 'choice',
                'values': [('976 SPS', BrickletIndustrialDualAnalogIn.SAMPLE_RATE_976_SPS),
                           ('488 SPS', BrickletIndustrialDualAnalogIn.SAMPLE_RATE_488_SPS),
                           ('244 SPS', BrickletIndustrialDualAnalogIn.SAMPLE_RATE_244_SPS),
                           ('122 SPS', BrickletIndustrialDualAnalogIn.SAMPLE_RATE_122_SPS),
                           ('61 SPS', BrickletIndustrialDualAnalogIn.SAMPLE_RATE_61_SPS),
                           ('4 SPS', BrickletIndustrialDualAnalogIn.SAMPLE_RATE_4_SPS),
                           ('2 SPS', BrickletIndustrialDualAnalogIn.SAMPLE_RATE_2_SPS),
                           ('1 SPS', BrickletIndustrialDualAnalogIn.SAMPLE_RATE_1_SPS)],
                'default': '2 SPS'
            }
        ]
    },
    BrickletIO16.DEVICE_DISPLAY_NAME: {
        'class': BrickletIO16,
        'values': [
            {
                'name': 'Port A',
                'getter': lambda device: value_to_bits(device.get_port('a'), 8),
                'subvalues': ['Pin 0', 'Pin 1', 'Pin 2', 'Pin 3', 'Pin 4', 'Pin 5', 'Pin 6', 'Pin 7'],
                'unit': [None, None, None, None, None, None, None, None],
                'advanced': False
            },
            {
                'name': 'Port B',
                'getter': lambda device: value_to_bits(device.get_port('b'), 8),
                'subvalues': ['Pin 0', 'Pin 1', 'Pin 2', 'Pin 3', 'Pin 4', 'Pin 5', 'Pin 6', 'Pin 7'],
                'unit': [None, None, None, None, None, None, None, None],
                'advanced': False
            },
            {
                'name': 'Edge Count (Pin A0)',
                'getter': lambda device: device.get_edge_count(0, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            },
            {
                'name': 'Edge Count (Pin A1)',
                'getter': lambda device: device.get_edge_count(1, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': lambda device, pinA0, pinA1, pinA2, pinA3, pinA4, pinA5, pinA6, pinA7,
                                         pinB0, pinB1, pinB2, pinB3, pinB4, pinB5, pinB6, pinB7,
                                         edge_count_type_pinA0, edge_count_debounce_pinA0, \
                                         edge_count_type_pinA1, edge_count_debounce_pinA1: \
                          [device.set_port_configuration(*pinA0),
                           device.set_port_configuration(*pinA1),
                           device.set_port_configuration(*pinA2),
                           device.set_port_configuration(*pinA3),
                           device.set_port_configuration(*pinA4),
                           device.set_port_configuration(*pinA5),
                           device.set_port_configuration(*pinA6),
                           device.set_port_configuration(*pinA7),
                           device.set_port_configuration(*pinB0),
                           device.set_port_configuration(*pinB1),
                           device.set_port_configuration(*pinB2),
                           device.set_port_configuration(*pinB3),
                           device.set_port_configuration(*pinB4),
                           device.set_port_configuration(*pinB5),
                           device.set_port_configuration(*pinB6),
                           device.set_port_configuration(*pinB7),
                           device.set_edge_count_config(0, edge_count_type_pinA0, edge_count_debounce_pinA0),
                           device.set_edge_count_config(1, edge_count_type_pinA1, edge_count_debounce_pinA1)],
        'options': [
            {
                'name': 'Pin A0',
                'type': 'choice',
                'values': [('Input Pull-Up', ('a', 0b00000001, 'i', True)),
                           ('Input', ('a', 0b00000001, 'i', False)),
                           ('Output High', ('a', 0b00000001, 'o', True)),
                           ('Output Low', ('a', 0b00000001, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin A1',
                'type': 'choice',
                'values': [('Input Pull-Up', ('a', 0b00000010, 'i', True)),
                           ('Input', ('a', 0b00000010, 'i', False)),
                           ('Output High', ('a', 0b00000010, 'o', True)),
                           ('Output Low', ('a', 0b00000010, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin A2',
                'type': 'choice',
                'values': [('Input Pull-Up', ('a', 0b00000100, 'i', True)),
                           ('Input', ('a', 0b00000100, 'i', False)),
                           ('Output High', ('a', 0b00000100, 'o', True)),
                           ('Output Low', ('a', 0b00000100, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin A3',
                'type': 'choice',
                'values': [('Input Pull-Up', ('a', 0b00001000, 'i', True)),
                           ('Input', ('a', 0b00001000, 'i', False)),
                           ('Output High', ('a', 0b00001000, 'o', True)),
                           ('Output Low', ('a', 0b00001000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin A4',
                'type': 'choice',
                'values': [('Input Pull-Up', ('a', 0b00010000, 'i', True)),
                           ('Input', ('a', 0b00010000, 'i', False)),
                           ('Output High', ('a', 0b00010000, 'o', True)),
                           ('Output Low', ('a', 0b00010000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin A5',
                'type': 'choice',
                'values': [('Input Pull-Up', ('a', 0b00100000, 'i', True)),
                           ('Input', ('a', 0b00100000, 'i', False)),
                           ('Output High', ('a', 0b00100000, 'o', True)),
                           ('Output Low', ('a', 0b00100000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin A6',
                'type': 'choice',
                'values': [('Input Pull-Up', ('a', 0b01000000, 'i', True)),
                           ('Input', ('a', 0b01000000, 'i', False)),
                           ('Output High', ('a', 0b01000000, 'o', True)),
                           ('Output Low', ('a', 0b01000000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin A7',
                'type': 'choice',
                'values': [('Input Pull-Up', ('a', 0b10000000, 'i', True)),
                           ('Input', ('a', 0b10000000, 'i', False)),
                           ('Output High', ('a', 0b10000000, 'o', True)),
                           ('Output Low', ('a', 0b10000000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin B0',
                'type': 'choice',
                'values': [('Input Pull-Up', ('b', 0b00000001, 'i', True)),
                           ('Input', ('b', 0b00000001, 'i', False)),
                           ('Output High', ('b', 0b00000001, 'o', True)),
                           ('Output Low', ('b', 0b00000001, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin B1',
                'type': 'choice',
                'values': [('Input Pull-Up', ('b', 0b00000010, 'i', True)),
                           ('Input', ('b', 0b00000010, 'i', False)),
                           ('Output High', ('b', 0b00000010, 'o', True)),
                           ('Output Low', ('b', 0b00000010, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin B2',
                'type': 'choice',
                'values': [('Input Pull-Up', ('b', 0b00000100, 'i', True)),
                           ('Input', ('b', 0b00000100, 'i', False)),
                           ('Output High', ('b', 0b00000100, 'o', True)),
                           ('Output Low', ('b', 0b00000100, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin B3',
                'type': 'choice',
                'values': [('Input Pull-Up', ('b', 0b00001000, 'i', True)),
                           ('Input', ('b', 0b00001000, 'i', False)),
                           ('Output High', ('b', 0b00001000, 'o', True)),
                           ('Output Low', ('b', 0b00001000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin B4',
                'type': 'choice',
                'values': [('Input Pull-Up', ('b', 0b00010000, 'i', True)),
                           ('Input', ('b', 0b00010000, 'i', False)),
                           ('Output High', ('b', 0b00010000, 'o', True)),
                           ('Output Low', ('b', 0b00010000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin B5',
                'type': 'choice',
                'values': [('Input Pull-Up', ('b', 0b00100000, 'i', True)),
                           ('Input', ('b', 0b00100000, 'i', False)),
                           ('Output High', ('b', 0b00100000, 'o', True)),
                           ('Output Low', ('b', 0b00100000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin B6',
                'type': 'choice',
                'values': [('Input Pull-Up', ('b', 0b01000000, 'i', True)),
                           ('Input', ('b', 0b01000000, 'i', False)),
                           ('Output High', ('b', 0b01000000, 'o', True)),
                           ('Output Low', ('b', 0b01000000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin B7',
                'type': 'choice',
                'values': [('Input Pull-Up', ('b', 0b10000000, 'i', True)),
                           ('Input', ('b', 0b10000000, 'i', False)),
                           ('Output High', ('b', 0b10000000, 'o', True)),
                           ('Output Low', ('b', 0b10000000, 'o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Edge Count Type (Pin A0)',
                'type': 'choice',
                'values': [('Rising', BrickletIO16.EDGE_TYPE_RISING),
                           ('Falling', BrickletIO16.EDGE_TYPE_FALLING),
                           ('Both', BrickletIO16.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin A0)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            },
            {
                'name': 'Edge Count Type (Pin A1)',
                'type': 'choice',
                'values': [('Rising', BrickletIO16.EDGE_TYPE_RISING),
                           ('Falling', BrickletIO16.EDGE_TYPE_FALLING),
                           ('Both', BrickletIO16.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin A1)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            }
        ]
    },
    BrickletIO4.DEVICE_DISPLAY_NAME: {
        'class': BrickletIO4,
        'values': [
            {
                'name': 'Value',
                'getter': lambda device: value_to_bits(device.get_value(), 4),
                'subvalues': ['Pin 0', 'Pin 1', 'Pin 2', 'Pin 3'],
                'unit': [None, None, None, None],
                'advanced': False
            },
            {
                'name': 'Edge Count (Pin 0)',
                'getter': lambda device: device.get_edge_count(0, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            },
            {
                'name': 'Edge Count (Pin 1)',
                'getter': lambda device: device.get_edge_count(1, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            },
            {
                'name': 'Edge Count (Pin 2)',
                'getter': lambda device: device.get_edge_count(2, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            },
            {
                'name': 'Edge Count (Pin 3)',
                'getter': lambda device: device.get_edge_count(3, False),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': lambda device, pin0, pin1, pin2, pin3,
                                         edge_count_type_pin0, edge_count_debounce_pin0, \
                                         edge_count_type_pin1, edge_count_debounce_pin1, \
                                         edge_count_type_pin2, edge_count_debounce_pin2, \
                                         edge_count_type_pin3, edge_count_debounce_pin3: \
                          [device.set_configuration(0b0001, *pin0),
                           device.set_configuration(0b0010, *pin1),
                           device.set_configuration(0b0100, *pin2),
                           device.set_configuration(0b1000, *pin3),
                           device.set_edge_count_config(0b0001, edge_count_type_pin0, edge_count_debounce_pin0),
                           device.set_edge_count_config(0b0010, edge_count_type_pin1, edge_count_debounce_pin1),
                           device.set_edge_count_config(0b0100, edge_count_type_pin2, edge_count_debounce_pin2),
                           device.set_edge_count_config(0b1000, edge_count_type_pin3, edge_count_debounce_pin3)],
        'options': [
            {
                'name': 'Pin 0',
                'type': 'choice',
                'values': [('Input Pull-Up', ('i', True)),
                           ('Input', ('i', False)),
                           ('Output High', ('o', True)),
                           ('Output Low', ('o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin 1',
                'type': 'choice',
                'values': [('Input Pull-Up', ('i', True)),
                           ('Input', ('i', False)),
                           ('Output High', ('o', True)),
                           ('Output Low', ('o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin 2',
                'type': 'choice',
                'values': [('Input Pull-Up', ('i', True)),
                           ('Input', ('i', False)),
                           ('Output High', ('o', True)),
                           ('Output Low', ('o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Pin 3',
                'type': 'choice',
                'values': [('Input Pull-Up', ('i', True)),
                           ('Input', ('i', False)),
                           ('Output High', ('o', True)),
                           ('Output Low', ('o', False))],
                'default': 'Input Pull-Up'
            },
            {
                'name': 'Edge Count Type (Pin 0)',
                'type': 'choice',
                'values': [('Rising', BrickletIndustrialDigitalIn4.EDGE_TYPE_RISING),
                           ('Falling', BrickletIndustrialDigitalIn4.EDGE_TYPE_FALLING),
                           ('Both', BrickletIndustrialDigitalIn4.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin 0)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            },
            {
                'name': 'Edge Count Type (Pin 1)',
                'type': 'choice',
                'values': [('Rising', BrickletIO4.EDGE_TYPE_RISING),
                           ('Falling', BrickletIO4.EDGE_TYPE_FALLING),
                           ('Both', BrickletIO4.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin 1)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            },
            {
                'name': 'Edge Count Type (Pin 2)',
                'type': 'choice',
                'values': [('Rising', BrickletIO4.EDGE_TYPE_RISING),
                           ('Falling', BrickletIO4.EDGE_TYPE_FALLING),
                           ('Both', BrickletIO4.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin 2)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            },
            {
                'name': 'Edge Count Type (Pin 3)',
                'type': 'choice',
                'values': [('Rising', BrickletIO4.EDGE_TYPE_RISING),
                           ('Falling', BrickletIO4.EDGE_TYPE_FALLING),
                           ('Both', BrickletIO4.EDGE_TYPE_BOTH)],
                'default': 'Rising'
            },
            {
                'name': 'Edge Count Debounce (Pin 3)',
                'type': 'int',
                'minimum': 0,
                'maximum': 255,
                'suffix': ' ms',
                'default': 100
            }
        ]
    },
    BrickletJoystick.DEVICE_DISPLAY_NAME: {
        'class': BrickletJoystick,
        'values': [
            {
                'name': 'Position',
                'getter': lambda device: device.get_position(),
                'subvalues': ['X', 'Y'],
                'unit': [None, None],
                'advanced': False
            },
            {
                'name': 'Pressed',
                'getter': lambda device: device.is_pressed(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': ['X', 'Y'],
                'unit': [None, None],
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletLEDStrip.DEVICE_DISPLAY_NAME: {
        'class': BrickletLEDStrip,
        'values': [
            {
                'name': 'Supply Voltage',
                'getter': lambda device: device.get_supply_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletLine.DEVICE_DISPLAY_NAME: {
        'class': BrickletLine,
        'values': [
            {
                'name': 'Reflectivity',
                'getter': lambda device: device.get_reflectivity(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletLinearPoti.DEVICE_DISPLAY_NAME: {
        'class': BrickletLinearPoti,
        'values': [
            {
                'name': 'Position',
                'getter': lambda device: device.get_position(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletLoadCell.DEVICE_DISPLAY_NAME: {
        'class': BrickletLoadCell,
        'values': [
            {
                'name': 'Weight',
                'getter': lambda device: device.get_weight(),
                'subvalues': None,
                'unit': 'gram',
                'advanced': False
            }
        ],
        'options_setter': lambda device, moving_average_length, rate, gain: \
                          [device.set_moving_average(moving_average_length), device.set_configuration(rate, gain)],
        'options': [
            {
                'name': 'Moving Average Length',
                'type': 'int',
                'minimum': 1,
                'maximum': 40,
                'suffix': None,
                'default': 4
            },
            {
                'name': 'Rate',
                'type': 'choice',
                'values': [('10Hz', BrickletLoadCell.RATE_10HZ),
                           ('80Hz', BrickletLoadCell.RATE_80HZ)],
                'default': '10Hz'
            },
            {
                'name': 'Gain',
                'type': 'choice',
                'values': [('128x', BrickletLoadCell.GAIN_128X),
                           ('64x', BrickletLoadCell.GAIN_64X),
                           ('32x', BrickletLoadCell.GAIN_32X)],
                'default': '128x'
            }
        ]
    },
    BrickletMoisture.DEVICE_DISPLAY_NAME: {
        'class': BrickletMoisture,
        'values': [
            {
                'name': 'Moisture Value',
                'getter': lambda device: device.get_moisture_value(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            }
        ],
        'options_setter': lambda device, moving_average_length: device.set_moving_average(moving_average_length),
        'options': [
            {
                'name': 'Moving Average Length',
                'type': 'int',
                'minimum': 0,
                'maximum': 100,
                'suffix': None,
                'default': 100
            }
        ]
    },
    BrickletMotionDetector.DEVICE_DISPLAY_NAME: {
        'class': BrickletMotionDetector,
        'values': [
            {
                'name': 'Motion Detected',
                'getter': lambda device: device.get_motion_detected(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletMultiTouch.DEVICE_DISPLAY_NAME: {
        'class': BrickletMultiTouch,
        'values': [
            {
                'name': 'State',
                'getter': lambda device: value_to_bits(device.get_touch_state(), 13),
                'subvalues': ['Electrode 0', 'Electrode 1', 'Electrode 2', 'Electrode 3', 'Electrode 4', 'Electrode 5',
                              'Electrode 6', 'Electrode 7', 'Electrode 8', 'Electrode 9', 'Electrode 10', 'Electrode 11', 'Proximity'],
                'unit': [None, None, None, None, None, None, None, None, None, None, None, None, None],
                'advanced': False
            }
        ],
        'options_setter': special_set_multi_touch_options,
        'options': [
            {
                'name': 'Electrode 0',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 1',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 2',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 3',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 4',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 5',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 6',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 7',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 8',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 9',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 10',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode 11',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Proximity',
                'type': 'bool',
                'default': True
            },
            {
                'name': 'Electrode Sensitivity',
                'type': 'int',
                'minimum': 5,
                'maximum': 201,
                'suffix': None,
                'default': 181
            }
        ]
    },
    BrickletPTC.DEVICE_DISPLAY_NAME: {
        'class': BrickletPTC,
        'values': [
            {
                'name': 'Temperature',
                'getter': special_get_ptc_temperature,
                'subvalues': None,
                'unit': '°C/100',
                'advanced': False
            },
            {
                'name': 'Resistance',
                'getter': special_get_ptc_resistance,
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': lambda device, wire_mode: device.set_wire_mode(wire_mode),
        'options': [
            {
                'name': 'Wire Mode',
                'type': 'choice',
                'values': [('2-Wire', BrickletPTC.WIRE_MODE_2),
                           ('3-Wire', BrickletPTC.WIRE_MODE_3),
                           ('4-Wire', BrickletPTC.WIRE_MODE_4)],
                'default': '2-Wire'
            }
        ]
    },
    BrickletRotaryEncoder.DEVICE_DISPLAY_NAME: {
        'class': BrickletRotaryEncoder,
        'values': [
            {
                'name': 'Count',
                'getter': lambda device: device.get_count(False),
                'subvalues': None,
                'unit': None,
                'advanced': False
            },
            {
                'name': 'Pressed',
                'getter': lambda device: device.is_pressed(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletRotaryPoti.DEVICE_DISPLAY_NAME: {
        'class': BrickletRotaryPoti,
        'values': [
            {
                'name': 'Position',
                'getter': lambda device: device.get_position(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletSoundIntensity.DEVICE_DISPLAY_NAME: {
        'class': BrickletSoundIntensity,
        'values': [
            {
                'name': 'Intensity',
                'getter': lambda device: device.get_intensity(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletTemperature.DEVICE_DISPLAY_NAME: {
        'class': BrickletTemperature,
        'values': [
            {
                'name': 'Temperature',
                'getter': lambda device: device.get_temperature(),
                'subvalues': None,
                'unit': '°C/100',
                'advanced': False
            }
        ],
        'options_setter': lambda device, i2c_mode: device.set_i2c_mode(i2c_mode),
        'options': [
            {
                'name': 'I2C Mode',
                'type': 'choice',
                'values': [('400kHz', BrickletTemperature.I2C_MODE_FAST),
                           ('100kHz', BrickletTemperature.I2C_MODE_SLOW)],
                'default': '400kHz'
            }
        ]
    },
    BrickletTemperatureIR.DEVICE_DISPLAY_NAME: {
        'class': BrickletTemperatureIR,
        'values': [
            {
                'name': 'Ambient Temperature',
                'getter': lambda device: device.get_ambient_temperature(),
                'subvalues': None,
                'unit': '°C/10',
                'advanced': False
            },
            {
                'name': 'Object Temperature',
                'getter': lambda device: device.get_object_temperature(),
                'subvalues': None,
                'unit': '°C/10',
                'advanced': False
            }
        ],
        'options_setter': lambda device, emissivity: device.set_emissivity(emissivity),
        'options': [
            {
                'name': 'Emissivity',
                'type': 'int',
                'minimum': 6553,
                'maximum': 65535,
                'suffix': None,
                'default': 65535
            }
        ]
    },
    BrickletTilt.DEVICE_DISPLAY_NAME: {
        'class': BrickletTilt,
        'values': [
            {
                'name': 'State',
                'getter': lambda device: device.get_tilt_state(),
                'subvalues': None,
                'unit': None,
                'advanced': False
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletVoltage.DEVICE_DISPLAY_NAME: {
        'class': BrickletVoltage,
        'values': [
            {
                'name': 'Voltage',
                'getter': lambda device: device.get_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'Analog Value',
                'getter': lambda device: device.get_analog_value(),
                'subvalues': None,
                'unit': None,
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickletVoltageCurrent.DEVICE_DISPLAY_NAME: {
        'class': BrickletVoltageCurrent,
        'values': [
            {
                'name': 'Voltage',
                'getter': lambda device: device.get_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'Current',
                'getter': lambda device: device.get_current(),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Power',
                'getter': lambda device: device.get_power(),
                'subvalues': None,
                'unit': 'mW',
                'advanced': False
            }
        ],
        'options_setter': lambda device, average_length, voltage_conversion_time, current_conversion_time: \
                          device.set_configuration(average_length, voltage_conversion_time, current_conversion_time),
        'options': [
            {
                'name': 'Average Length',
                'type': 'choice',
                'values': [('1', BrickletVoltageCurrent.AVERAGING_1),
                           ('4', BrickletVoltageCurrent.AVERAGING_4),
                           ('16', BrickletVoltageCurrent.AVERAGING_16),
                           ('64', BrickletVoltageCurrent.AVERAGING_64),
                           ('128', BrickletVoltageCurrent.AVERAGING_128),
                           ('256', BrickletVoltageCurrent.AVERAGING_256),
                           ('512', BrickletVoltageCurrent.AVERAGING_512),
                           ('1024', BrickletVoltageCurrent.AVERAGING_1024)],
                'default': '64'
            },
            {
                'name': 'Voltage Conversion Time',
                'type': 'choice',
                'values': [('140µs', 0),
                           ('204µs', 1),
                           ('332µs', 2),
                           ('588µs', 3),
                           ('1.1ms', 4),
                           ('2.116ms', 5),
                           ('4.156ms', 6),
                           ('8.244ms', 7)],
                'default': '1.1ms'
            },
            {
                'name': 'Current Conversion Time',
                'type': 'choice',
                'values': [('140µs', 0),
                           ('204µs', 1),
                           ('332µs', 2),
                           ('588µs', 3),
                           ('1.1ms', 4),
                           ('2.116ms', 5),
                           ('4.156ms', 6),
                           ('8.244ms', 7)],
                'default': '1.1ms'
            }
        ]
    },
    BrickDC.DEVICE_DISPLAY_NAME: {
        'class': BrickDC,
        'values': [
            {
                'name': 'Stack Input Voltage',
                'getter': lambda device: device.get_stack_input_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'External Input Voltage',
                'getter': lambda device: device.get_external_input_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'Current Consumption',
                'getter': lambda device: device.get_current_consumption(),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Chip Temperature',
                'getter': lambda device: device.get_chip_temperature(),
                'subvalues': None,
                'unit': '°C/10',
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickIMU.DEVICE_DISPLAY_NAME: {
        'class': BrickIMU,
        'values': [
            {
                'name': 'Orientation',
                'getter': lambda device: device.get_orientation(),
                'subvalues': ['Roll', 'Pitch', 'Yaw'],
                'unit': ['°/100', '°/100', '°/100'],
                'advanced': False
            },
            {
                'name': 'Quaternion',
                'getter': lambda device: device.get_quaternion(),
                'subvalues': ['X', 'Y', 'Z', 'W'],
                'unit': [None, None, None, None],
                'advanced': False
            },
            {
                'name': 'Acceleration',
                'getter': lambda device: device.get_acceleration(),
                'subvalues': ['X', 'Y', 'Z'],
                'unit': ['g/1000', 'g/1000', 'g/1000'],
                'advanced': True
            },
            {
                'name': 'Magnetic Field',
                'getter': lambda device: device.get_magnetic_field(),
                'subvalues': ['X', 'Y', 'Z'],
                'unit': ['G/1000', 'G/1000', 'G/1000'],
                'advanced': True
            },
            {
                'name': 'Angular Velocity',
                'getter': lambda device: device.get_angular_velocity(),
                'subvalues': ['X', 'Y', 'Z'],
                'unit': ['8/115 °/s', '8/115 °/s', '8/115 °/s'],
                'advanced': True
            },
            {
                'name': 'IMU Temperature',
                'getter': lambda device: device.get_imu_temperature(),
                'subvalues': None,
                'unit': '°C/100',
                'advanced': True
            },
            {
                'name': 'All Data',
                'getter': lambda device: device.get_all_data(),
                'subvalues': ['Acceleration-X', 'Acceleration-Y', 'Acceleration-Z', 'Acceleration-X', 'Acceleration-Y', 'Acceleration-Z',
                              'Angular Velocity-X', 'Angular Velocity-Y', 'Angular Velocity-Z', 'IMU Temperature'],
                'unit': ['g/1000', 'g/1000', 'g/1000', 'G/1000', 'G/1000', 'G/1000', '8/115 °/s', '8/115 °/s', '8/115 °/s', '°C/100'],
                'advanced': True
            },
            {
                'name': 'Chip Temperature',
                'getter': lambda device: device.get_chip_temperature(),
                'subvalues': None,
                'unit': '°C/10',
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None # FIXME: ranges
    },
    BrickIMUV2.DEVICE_DISPLAY_NAME: {
        'class': BrickIMUV2,
        'values': [
            {
                'name': 'Orientation',
                'getter': lambda device: device.get_orientation(),
                'subvalues': ['Heading', 'Roll', 'Pitch'],
                'unit': ['°/16', '°/16', '°/16'],
                'advanced': False
            },
            {
                'name': 'Linear Acceleration',
                'getter': lambda device: device.get_linear_acceleration(),
                'subvalues': ['X', 'Y', 'Z'],
                'unit': ['1/100 m/s²', '1/100 m/s²', '1/100 m/s²'],
                'advanced': False
            },
            {
                'name': 'Gravity Vector',
                'getter': lambda device: device.get_gravity_vector(),
                'subvalues': ['X', 'Y', 'Z'],
                'unit': ['1/100 m/s²', '1/100 m/s²', '1/100 m/s²'],
                'advanced': False
            },
            {
                'name': 'Quaternion',
                'getter': lambda device: device.get_quaternion(),
                'subvalues': ['W', 'X', 'Y', 'Z'],
                'unit': ['1/16383', '1/16383', '1/16383', '1/16383'],
                'advanced': False
            },
            {
                'name': 'Acceleration',
                'getter': lambda device: device.get_acceleration(),
                'subvalues': ['X', 'Y', 'Z'],
                'unit': ['1/100 m/s²', '1/100 m/s²', '1/100 m/s²'],
                'advanced': True
            },
            {
                'name': 'Magnetic Field',
                'getter': lambda device: device.get_magnetic_field(),
                'subvalues': ['X', 'Y', 'Z'],
                'unit': ['1/16 µT ', '1/16 µT ', '1/16 µT '],
                'advanced': True
            },
            {
                'name': 'Angular Velocity',
                'getter': lambda device: device.get_angular_velocity(),
                'subvalues': ['X', 'Y', 'Z'],
                'unit': ['1/16 °/s', '1/16 °/s', '1/16 °/s'],
                'advanced': True
            },
            {
                'name': 'Temperature',
                'getter': lambda device: device.get_temperature(),
                'subvalues': None,
                'unit': '°C/100',
                'advanced': True
            },
            #{
            #    'name': 'All Data',
            #    'getter': lambda device: device.get_all_data(),
            #    'subvalues': # FIXME: nested arrays
            #    'unit': # FIXME: nested arrays
            #    'advanced': False
            #},
            {
                'name': 'Chip Temperature',
                'getter': lambda device: device.get_chip_temperature(),
                'subvalues': None,
                'unit': '°C/10',
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None # FIXME: ranges
    },
    BrickMaster.DEVICE_DISPLAY_NAME: {
        'class': BrickMaster,
        'values': [
            {
                'name': 'Stack Voltage',
                'getter': lambda device: device.get_stack_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'Stack Current',
                'getter': lambda device: device.get_stack_current(),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Chip Temperature',
                'getter': lambda device: device.get_chip_temperature(),
                'subvalues': None,
                'unit': '°C/10',
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickServo.DEVICE_DISPLAY_NAME: {
        'class': BrickServo,
        'values': [
            {
                'name': 'Servo Current (Servo 0)',
                'getter': lambda device: device.get_servo_current(0),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Servo Current (Servo 1)',
                'getter': lambda device: device.get_servo_current(1),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Servo Current (Servo 2)',
                'getter': lambda device: device.get_servo_current(2),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Servo Current (Servo 3)',
                'getter': lambda device: device.get_servo_current(3),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Servo Current (Servo 4)',
                'getter': lambda device: device.get_servo_current(4),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Servo Current (Servo 5)',
                'getter': lambda device: device.get_servo_current(5),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Servo Current (Servo 6)',
                'getter': lambda device: device.get_servo_current(6),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Overall Current',
                'getter': lambda device: device.get_overall_current(),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Stack Input Voltage',
                'getter': lambda device: device.get_stack_input_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'External Input Voltage',
                'getter': lambda device: device.get_external_input_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'Chip Temperature',
                'getter': lambda device: device.get_chip_temperature(),
                'subvalues': None,
                'unit': '°C/10',
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    },
    BrickStepper.DEVICE_DISPLAY_NAME: {
        'class': BrickStepper,
        'values': [
            {
                'name': 'Stack Input Voltage',
                'getter': lambda device: device.get_stack_input_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'External Input Voltage',
                'getter': lambda device: device.get_external_input_voltage(),
                'subvalues': None,
                'unit': 'mV',
                'advanced': False
            },
            {
                'name': 'Current Consumption',
                'getter': lambda device: device.get_current_consumption(),
                'subvalues': None,
                'unit': 'mA',
                'advanced': False
            },
            {
                'name': 'Chip Temperature',
                'getter': lambda device: device.get_chip_temperature(),
                'subvalues': None,
                'unit': '°C/10',
                'advanced': True
            }
        ],
        'options_setter': None,
        'options': None
    }
}

'''
/*---------------------------------------------------------------------------
                                AbstractDevice
 ---------------------------------------------------------------------------*/
 '''

class AbstractDevice(object):
    """DEBUG and Inheritance only class"""

    def __init__(self, data, datalogger):
        self.datalogger = datalogger
        self.data = data

        self.__name__ = "AbstractDevice"

    def start_timer(self):
        """
        Starts all timer for all loggable variables of the devices.
        """
        EventLogger.debug(self.__str__())

    def _try_catch(self, func):
        """
        Creates a simple try-catch for a specific funtion.
        """
        value = "[NYI-FAIL-TIMER]"
        # err = 0
        try:
            value = func()
        except Exception as e:
            value = self._exception_msg(e.value, e.description)
            # err = 1
        return value

    def _exception_msg(self, value, msg):
        """
        For a uniform creation of Exception messages.
        """
        return "ERROR[" + str(value) + "]: " + str(msg)

    def __str__(self):
        """
        Representation String of the class. For simple overwiev.
        """
        return "[" + str(self.__name__) + "]"

'''
/*---------------------------------------------------------------------------
                                DeviceImpl
 ---------------------------------------------------------------------------*/
 '''

class DeviceImpl(AbstractDevice):
    """
    A SimpleDevice is every device, which only has funtion with one return value.
    """

    def __init__(self, data, datalogger):
        AbstractDevice.__init__(self, data, datalogger)

        self.device_name = self.data['name']
        self.device_uid = self.data['uid']
        self.device_spec = device_specs[self.device_name]
        device_class = self.device_spec['class']
        self.device = device_class(self.device_uid, self.datalogger.ipcon)

        self.__name__ = "devices:" + str(self.device_name)

    def start_timer(self):
        AbstractDevice.start_timer(self)

        for value in self.data['values']:
            interval = self.data['values'][value]['interval']
            func_name = "_timer"
            var_name = value

            self.datalogger.timers.append(LoggerTimer(interval, func_name, var_name, self))

    def apply_options(self):
        options_setter = self.device_spec['options_setter']
        option_specs = self.device_spec['options']

        if options_setter != None and option_specs != None:
            EventLogger.debug('Applying options for "{0}" with UID "{1}"'.format(self.device_name, self.device_uid))

            args = []

            for option_spec in option_specs:
                for option_name in self.data['options']:
                    if option_name == option_spec['name']:
                        option_value = self.data['options'][option_name]['value']

                        if option_spec['type'] == 'choice':
                            for option_value_spec in option_spec['values']:
                                if option_value == option_value_spec[0]:
                                    args.append(option_value_spec[1])
                        elif option_spec['type'] == 'int':
                            args.append(option_value)
                        elif option_spec['type'] == 'bool':
                            args.append(option_value)

            try:
                options_setter(self.device, *tuple(args))
            except Exception as e:
                EventLogger.warning('Could not apply options for "{0}" with UID "{1}": {2}'
                                    .format(self.device_name, self.device_uid, e))

    def _timer(self, var_name):
        """
        This function is used by the LoggerTimer to get the variable values from the brickd.
        In SimpleDevices the get-functions only return one value.
        """

        for value_spec in self.device_spec['values']:
            if value_spec['name'] == var_name:
                break

        getter = value_spec['getter']
        subvalue_names = value_spec['subvalues']
        unit = value_spec['unit']
        now = time.time()
        time_format = self.datalogger._config['data']['time_format']
        time_format_strftime = self.datalogger._config['data']['time_format_strftime']

        if time_format == 'de':
            timestamp = timestamp_to_de(now)
        elif time_format == 'de-msec':
            timestamp = timestamp_to_de_msec(now)
        elif time_format == 'us':
            timestamp = timestamp_to_us(now)
        elif time_format == 'us-msec':
            timestamp = timestamp_to_us_msec(now)
        elif time_format == 'iso':
            timestamp = timestamp_to_iso(now)
        elif time_format == 'iso-msec':
            timestamp = timestamp_to_iso_msec(now)
        elif time_format == 'unix':
            timestamp = timestamp_to_unix(now)
        elif time_format == 'unix-msec':
            timestamp = timestamp_to_unix_msec(now)
        elif time_format == 'strftime':
            timestamp = timestamp_to_strftime(now, time_format_strftime)
        else:
            timestamp = timestamp_to_unix(now)

        try:
            value = getter(self.device)
        except Exception as e:
            value = self._exception_msg(str(self.device_name) + "-" + str(var_name), e)
            self.datalogger.add_to_queue(CSVData(timestamp,
                                                 self.device_name,
                                                 self.device_uid,
                                                 var_name,
                                                 value,
                                                 ''))
            # log_exception(timestamp, value_name, e)
            return

        try:
            if subvalue_names is None:
                if unit == None:
                    unit_str = ''
                else:
                    unit_str = unit

                # log_value(value_name, value)
                self.datalogger.add_to_queue(CSVData(timestamp,
                                                     self.device_name,
                                                     self.device_uid,
                                                     var_name,
                                                     value,
                                                     unit_str))
            else:
                subvalue_bool = self.data['values'][var_name]['subvalues']
                for i in range(len(subvalue_names)):
                    if not isinstance(subvalue_names[i], list):
                        try:
                            if subvalue_bool[subvalue_names[i]]:
                                if unit[i] == None:
                                    unit_str = ''
                                else:
                                    unit_str = unit[i]
                                self.datalogger.add_to_queue(CSVData(timestamp,
                                                                     self.device_name,
                                                                     self.device_uid,
                                                                     str(var_name) + "-" + str(subvalue_names[i]),
                                                                     value[i],
                                                                     unit_str))
                        except Exception as e:
                            value = self._exception_msg(str(self.device_name) + "-" + str(var_name), e)
                            self.datalogger.add_to_queue(CSVData(timestamp,
                                                                 self.device_name,
                                                                 self.device_uid,
                                                                 str(var_name) + "-" + str(subvalue_names[i]),
                                                                 value[i],
                                                                 ''))
                            return
                    else:
                        for k in range(len(subvalue_names[i])):
                            try:
                                if subvalue_bool[subvalue_names[i][k]]:
                                    if unit[i][k] == None:
                                        unit_str = ''
                                    else:
                                        unit_str = unit[i][k]
                                    self.datalogger.add_to_queue(CSVData(timestamp,
                                                                         self.device_name,
                                                                         self.device_uid,
                                                                         str(var_name) + "-" + str(subvalue_names[i][k]),
                                                                         value[i][k],
                                                                         unit_str))
                            except Exception as e:
                                value = self._exception_msg(str(self.device_name) + "-" + str(var_name), e)
                                self.datalogger.add_to_queue(CSVData(timestamp,
                                                                     self.device_name,
                                                                     self.device_uid,
                                                                     str(var_name) + "-" + str(subvalue_names[i][k]),
                                                                     value[i][k],
                                                                     ''))
                                return
        except Exception as e:
            value = self._exception_msg(str(self.device_name) + "-" + str(var_name), e)
            self.datalogger.add_to_queue(CSVData(timestamp,
                                                 self.device_name,
                                                 self.device_uid,
                                                 var_name,
                                                 value,
                                                 ''))



""""
/*---------------------------------------------------------------------------
                                Jobs
 ---------------------------------------------------------------------------*/
"""
from PyQt4 import QtCore
import Queue
import threading
import time

if 'merged_data_logger_modules' not in globals():
    from brickv.data_logger.event_logger import EventLogger
    from brickv.data_logger.utils import CSVWriter

class AbstractJob(threading.Thread):
    def __init__(self, datalogger=None, group=None, target=None, name=None, args=(), kwargs=None, verbose=None):
        threading.Thread.__init__(self, group=group, target=target, name=name, args=args, kwargs=kwargs,
                                  verbose=verbose)

        self.daemon = True
        self._exit_flag = False
        self._datalogger = datalogger
        self._job_name = "[Job:" + self.name + "]"

        if self._datalogger is not None:
            self._datalogger.data_queue[self.name] = Queue.Queue()

    def stop(self):
        self._exit_flag = True

    def _job(self):
        # check for datalogger object
        if self._datalogger is None:
            EventLogger.warning(self.name + " started but did not get a DataLogger Object! No work could be done.")
            return True
        return False

    def _get_data_from_queue(self):
        if self._datalogger is not None:
            return self._datalogger.data_queue[self.name].get()
        return None

    # Needs to be called when you end the job!
    def _remove_from_data_queue(self):
        try:
            self._datalogger.data_queue.pop(self.name)
        except KeyError as key_err:
            EventLogger.warning("Job:" + self.name + " was not in the DataQueue! -> " + str(key_err))


class CSVWriterJob(AbstractJob):
    """
    This class enables the data logger to write logged data to an CSV formatted file
    """

    def __init__(self, datalogger=None, group=None, name="CSVWriterJob", args=(), kwargs=None, verbose=None):
        target = self._job
        AbstractJob.__init__(self, datalogger=datalogger, group=group, target=target, name=name, args=args,
                             kwargs=kwargs, verbose=verbose)

    def _job(self):
        try:
            # check for datalogger object
            if AbstractJob._job(self):
                return

            EventLogger.debug(self._job_name + " Started")
            csv_writer = CSVWriter(self._datalogger.csv_file_name)

            while True:
                if not self._datalogger.data_queue[self.name].empty():
                    csv_data = self._get_data_from_queue()
                    #EventLogger.debug(self._job_name + " -> " + str(csv_data))
                    if not csv_writer.write_data_row(csv_data):
                        EventLogger.warning(self._job_name + " Could not write csv row!")

                if not self._exit_flag and self._datalogger.data_queue[self.name].empty():
                    time.sleep(self._datalogger.job_sleep)

                if self._exit_flag and self._datalogger.data_queue[self.name].empty():
                    exit_return_value = csv_writer.close_file()
                    if exit_return_value:
                        EventLogger.debug(self._job_name + " Closed his csv_writer")
                    else:
                        EventLogger.debug(
                            self._job_name + " Could NOT close his csv_writer! EXIT_RETURN_VALUE=" + str(exit))
                    EventLogger.debug(self._job_name + " Finished")

                    self._remove_from_data_queue()
                    break

        except Exception as e:
            EventLogger.critical(self._job_name + " " + str(e))
            self.stop()


class GuiDataJob(AbstractJob, QtCore.QObject):
    """
    This class enables the data logger to upload logged data to the Xively platform
    """

    SIGNAL_NEW_DATA = "signalNewData"

    def __init__(self, datalogger=None, group=None, name="GuiDataJob", args=(), kwargs=None, verbose=None):
        target = self._job
        AbstractJob.__init__(self, datalogger=datalogger, group=group, target=target, name=name, args=args,
                             kwargs=kwargs, verbose=verbose)
        QtCore.QObject.__init__(self)

    def set_datalogger(self, datalogger):
        self._datalogger = datalogger
        self._datalogger.data_queue[self.name] = Queue.Queue()

    def _job(self):
        try:
            # check for datalogger object
            if AbstractJob._job(self):
                return

            EventLogger.debug(self._job_name + " Started")

            while True:
                if not self._datalogger.data_queue[self.name].empty():
                    csv_data = self._get_data_from_queue()
                    #EventLogger.debug(self._job_name + " -> " + str(csv_data))
                    self.emit(QtCore.SIGNAL(GuiDataJob.SIGNAL_NEW_DATA), csv_data)

                if not self._exit_flag and self._datalogger.data_queue[self.name].empty():
                    time.sleep(self._datalogger.job_sleep)

                if self._exit_flag and self._datalogger.data_queue[self.name].empty():
                    self._remove_from_data_queue()
                    break

        except Exception as e:
            EventLogger.critical(self._job_name + " -.- " + str(e))
            self.stop()


class XivelyJob(AbstractJob):
    """
    This class enables the data logger to upload logged data to the Xively platform
    """

    def __init__(self, datalogger=None, group=None, name="XivelyJob", args=(), kwargs=None, verbose=None):
        super(XivelyJob, self).__init__()
        EventLogger.warning(self._job_name + " Is not supported!")
        raise Exception("XivelyJob not yet implemented!")


    def _job(self):
        EventLogger.warning(self._job_name + " Is not supported!")
        raise Exception("XivelyJob._job not yet implemented!")

        # TODO: implement xively logger
        # try:
        # # check for datalogger object
        # if AbstractJob._job(self):
        # return
        #
        # EventLogger.debug(self._job_name + " Started")
        #
        # while (True):
        #         if not self._datalogger.data_queue[self.name].empty():
        #             # write
        #             csv_data = self._get_data_from_queue()
        #             EventLogger.debug(self._job_name + " -> " + str(csv_data))
        #
        #         if not self._exit_flag and self._datalogger.data_queue[self.name].empty():
        #             time.sleep(self._datalogger.job_sleep)
        #
        #         if self._exit_flag and self._datalogger.data_queue[self.name].empty():
        #             # close job
        #             EventLogger.debug(self._job_name + " Finished")
        #
        #             self._remove_from_data_queue()
        #             break
        #
        # except Exception as e:
        #     EventLogger.critical(self._job_name + " " + str(e))
        #     self.stop()



import logging
import threading
import time

if 'merged_data_logger_modules' not in globals():
    from brickv.bindings.ip_connection import IPConnection, base58decode
    from brickv.data_logger.event_logger import EventLogger
    from brickv.data_logger.job import CSVWriterJob#, GuiDataJob
    from brickv.data_logger.loggable_devices import DeviceImpl
    from brickv.data_logger.utils import DataLoggerException
else:
    from tinkerforge.ip_connection import IPConnection, base58decode

class DataLogger(threading.Thread):
    """
    This class represents the data logger and an object of this class is
    the actual instance of a logging process
    """

    # constructor and other functions
    def __init__(self, config, gui_job):
        super(DataLogger, self).__init__()

        self.daemon = True

        self.jobs = []  # thread hashmap for all running threads/jobs
        self.job_exit_flag = False  # flag for stopping the thread
        self.job_sleep = 1  # TODO: Enahncement -> use condition objects
        self.timers = []
        self._gui_job = gui_job
        self.data_queue = {}  # universal data_queue hash map
        self.host = config['hosts']['default']['name']
        self.port = config['hosts']['default']['port']
        self.loggable_devices = []
        self.ipcon = IPConnection()

        self.ipcon.register_callback(IPConnection.CALLBACK_CONNECTED, self.cb_connected)
        self.ipcon.register_callback(IPConnection.CALLBACK_ENUMERATE, self.cb_enumerate)

        try:
            self.ipcon.connect(self.host, self.port)  # Connect to brickd
        except Exception as e:
            EventLogger.critical("A critical error occur: " + str(e))
            self.ipcon = None
            raise DataLoggerException(DataLoggerException.DL_CRITICAL_ERROR, "A critical error occur: " + str(e))

        EventLogger.info("Connection to " + self.host + ":" + str(self.port) + " established.")
        self.ipcon.set_timeout(1)  # TODO: Timeout number
        EventLogger.debug("Set ipcon.time_out to 1.")
        self._config = config
        self.csv_file_name = 'logger_data_{0}.csv'.format(int(time.time()))
        self.csv_enabled = True
        self.stopped = False

    def cb_connected(self, connect_reason):
        self.apply_options()

    def cb_enumerate(self, uid, connected_uid, position,
                     hardware_version, firmware_version,
                     device_identifier, enumeration_type):
        if enumeration_type in [IPConnection.ENUMERATION_TYPE_AVAILABLE,
                                IPConnection.ENUMERATION_TYPE_CONNECTED]:
            self.apply_options()

    def apply_options(self):
        for loggable_device in self.loggable_devices:
            loggable_device.apply_options()

    def process_data_csv_section(self):
        """
        Information out of the general section will be consumed here
        """
        csv = self._config['data']['csv']

        self.csv_enabled = csv['enabled']
        self.csv_file_name = csv['file_name']

        if self.csv_enabled:
            EventLogger.info("Logging data to CSV file: " + str(self.csv_file_name))

    def initialize_loggable_devices(self):
        """
        This function creates the actual objects for each device out of the configuration
        """
        # start the timers
        for device in self._config['devices']:
            if len(device['uid']) == 0:
                EventLogger.warning('Ignoring "{0}" with empty UID'.format(device['name']))
                continue

            try:
                decoded_uid = base58decode(device['uid'])
            except:
                EventLogger.warning('Ignoring "{0}" with invalid UID: {1}'.format(device['name'], device['uid']))
                continue

            if decoded_uid < 1 or decoded_uid > 0xFFFFFFFF:
                EventLogger.warning('Ignoring "{0}" with out-of-range UID: {1}'.format(device['name'], device['uid']))
                continue

            try:
                loggable_device = DeviceImpl(device, self)
                loggable_device.start_timer()
            except Exception as e:
                msg = "A critical error occur: " + str(e)
                self.stop()
                raise DataLoggerException(DataLoggerException.DL_CRITICAL_ERROR, msg)

            self.loggable_devices.append(loggable_device)

        self.apply_options()

    def run(self):
        """
        This function starts the actual logging process in a new thread
        """
        self.stopped = False
        self.process_data_csv_section()

        self.initialize_loggable_devices()

        """START-WRITE-THREAD"""
        # create jobs
        # look which thread should be working
        if self.csv_enabled:
            self.jobs.append(CSVWriterJob(name="CSV-Writer", datalogger=self))
        if self._gui_job is not None:
            self._gui_job.set_datalogger(self)
            self.jobs.append(self._gui_job)

        for t in self.jobs:
            t.start()
        EventLogger.debug("Jobs started.")

        """START-TIMERS"""
        for t in self.timers:
            t.start()
        EventLogger.debug("Get-Timers started.")

        """END_CONDITIONS"""
        EventLogger.info("DataLogger is running...")
        # TODO Exit condition ?

    def stop(self):
        """
        This function ends the logging process. self.stopped will be set to True if
        the data logger stops
        """
        EventLogger.info("Closing Timers and Threads...")

        """CLEANUP_AFTER_STOP """
        # check if all timers stopped
        for t in self.timers:
            t.stop()
        for t in self.timers:
            t.join()
        EventLogger.debug("Get-Timers[" + str(len(self.timers)) + "] stopped.")

        # set THREAD_EXIT_FLAG for all work threads
        for job in self.jobs:
            job.stop()
        # wait for all threads to stop
        for job in self.jobs:
            job.join()
        EventLogger.debug("Jobs[" + str(len(self.jobs)) + "] stopped.")

        if self.ipcon is not None and self.ipcon.get_connection_state() == IPConnection.CONNECTION_STATE_CONNECTED:
            self.ipcon.disconnect()
        EventLogger.info("Connection closed successfully.")

        self.stopped = True

    def add_to_queue(self, csv):
        """
        Adds logged data to all queues which are registered in 'self.data_queue'

        csv --
        """
        for q in self.data_queue.values():
            q.put(csv)



"""
/*---------------------------------------------------------------------------
                                Event Logger
 ---------------------------------------------------------------------------*/
"""
from PyQt4 import QtCore
from PyQt4.QtCore import SIGNAL

import logging
from datetime import datetime

class EventLogger():
    """
        Basic EventLogger class.
    """

    format = "%(asctime)s - %(levelname)8s - %(message)s"
    __loggers = {}

    def __init__(self):
        pass

    def add_logger(logger):
        if logger.name is None or logger.name == "":
            raise Exception("Logger has no Attribute called 'name'!")

        EventLogger.__loggers[logger.name] = logger

    def remove_logger(logger_name):
        if logger_name in EventLogger.__loggers:
            EventLogger.__loggers.pop(logger_name)
            return True

        return False

    # Does not really work as expected >_>
    # def get_logger(logger_name):
    #     if logger_name in EventLogger.__loggers:
    #         return EventLogger.__loggers.get(logger_name)
    #     return None

    def debug(msg, logger_name=None):
        level = logging.DEBUG
        EventLogger._send_message(level, msg, logger_name)

    def info(msg, logger_name=None):
        level = logging.INFO
        EventLogger._send_message(level, msg, logger_name)

    def warn(msg, logger_name=None):
        level = logging.WARN
        EventLogger._send_message(level, msg, logger_name)

    def warning(msg, logger_name=None):
        level = logging.WARNING
        EventLogger._send_message(level, msg, logger_name)

    def error(msg, logger_name=None):
        level = logging.ERROR
        EventLogger._send_message(level, msg, logger_name)

    def critical(msg, logger_name=None):
        level = logging.CRITICAL
        EventLogger._send_message(level, msg, logger_name)

    def log(level, msg, logger_name=None):
        EventLogger._send_message(level, msg, logger_name)

    def _send_message(level, msg, logger_name):
        if logger_name is not None:
            if logger_name in EventLogger.__loggers:
                EventLogger.__loggers[logger_name].log(level, msg)
        else:
            for logger in EventLogger.__loggers.values():
                logger.log(level, msg)

    # static methods
    add_logger = staticmethod(add_logger)
    remove_logger = staticmethod(remove_logger)
    # get_logger = staticmethod(get_logger)
    debug = staticmethod(debug)
    info = staticmethod(info)
    warn = staticmethod(warn)
    warning = staticmethod(warning)
    error = staticmethod(error)
    critical = staticmethod(critical)
    log = staticmethod(log)
    _send_message = staticmethod(_send_message)


class ConsoleLogger(logging.Logger):
    """
    This class outputs the logged debug messages to the console
    """

    def __init__(self, name, log_level):
        logging.Logger.__init__(self, name, log_level)

        # create console handler and set level
        ch = logging.StreamHandler()

        ch.setLevel(log_level)

        # create formatter
        formatter = logging.Formatter(EventLogger.format)

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        self.addHandler(ch)

class FileLogger(logging.Logger):
    """
    This class writes the logged debug messages to a log file
    """

    def __init__(self, name, log_level, filename):
        logging.Logger.__init__(self, name, log_level)

        ch = logging.FileHandler(filename, mode="a")

        ch.setLevel(log_level)

        # create formatter
        formatter = logging.Formatter(EventLogger.format)

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        self.addHandler(ch)

        self.info("###### NEW LOGGING SESSION STARTED ######")

class GUILogger(logging.Logger, QtCore.QObject):
    """
    This class outputs the logged data to the brickv gui
    """

    _output_format = "{asctime} - <b>{levelname:8}</b> - {message}"
    _output_format_warning = "<font color=\"orange\">{asctime} - <b>{levelname:8}</b> - {message}</font>"
    _output_format_critical = "<font color=\"red\">{asctime} - <b>{levelname:8}</b> - {message}</font>"

    SIGNAL_NEW_MESSAGE = "newEventMessage"
    SIGNAL_NEW_MESSAGE_TAB_HIGHLIGHT = "newEventTabHighlight"

    def __init__(self, name, log_level):
        logging.Logger.__init__(self, name, log_level)
        QtCore.QObject.__init__(self)

    def debug(self, msg):
        self.log(logging.DEBUG, msg)

    def info(self, msg):
        self.log(logging.INFO, msg)

    def warn(self, msg):
        self.log(logging.WARN, msg)

    def warning(self, msg):
        self.log(logging.WARNING, msg)

    def critical(self, msg):
        self.log(logging.CRITICAL, msg)

    def error(self, msg):
        self.log(logging.ERROR, msg)

    def log(self, level, msg):
        if level >= self.level:
            asctime = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.now())
            levelname = logging._levelNames.get(level)

            if level == logging.WARN or level == logging.WARNING:
                self.emit(SIGNAL(GUILogger.SIGNAL_NEW_MESSAGE),
                          GUILogger._output_format_warning.format(asctime=asctime, levelname=levelname, message=msg))
                self.emit(SIGNAL(GUILogger.SIGNAL_NEW_MESSAGE_TAB_HIGHLIGHT))
            elif level == logging.CRITICAL or level == logging.ERROR:
                self.emit(SIGNAL(GUILogger.SIGNAL_NEW_MESSAGE),
                          GUILogger._output_format_critical.format(asctime=asctime, levelname=levelname, message=msg))
                self.emit(SIGNAL(GUILogger.SIGNAL_NEW_MESSAGE_TAB_HIGHLIGHT))
            else:
                self.emit(SIGNAL(GUILogger.SIGNAL_NEW_MESSAGE),
                          GUILogger._output_format.format(asctime=asctime, levelname=levelname, message=msg))



# MAIN DATA_LOGGER PROGRAM
import argparse  # command line argument parser
import os
import signal
import sys
import traceback
import logging
import functools
import time
import locale

if 'merged_data_logger_modules' not in globals():
    from brickv.data_logger.data_logger import DataLogger
    from brickv.data_logger.event_logger import ConsoleLogger, FileLogger, EventLogger
    from brickv.data_logger.utils import DataLoggerException
    from brickv.data_logger.configuration import load_and_validate_config

def signal_handler(interrupted_ref, signum, frame):
    """
    This function handles the ctrl + c exit condition
    if it's raised through the console
    """
    EventLogger.info('Received SIGINT/SIGTERM')
    interrupted_ref[0] = True

def log_level_name_to_id(log_level):
    if log_level == 'debug':
        return logging.DEBUG
    elif log_level == 'info':
        return logging.INFO
    elif log_level == 'warning':
        return logging.WARNING
    elif log_level == 'error':
        return logging.ERROR
    elif log_level == 'critical':
        return logging.CRITICAL
    else:
        return logging.INFO

def main(config_filename, gui_config, gui_job, override_csv_file_name,
         override_log_file_name, interrupted_ref):
    """
    This function initialize the data logger and starts the logging process
    """
    config = None
    gui_start = False

    if config_filename != None: # started via console
        config = load_and_validate_config(config_filename)

        if config == None:
            return None
    else: # started via GUI
        config = gui_config
        gui_start = True

    if override_csv_file_name != None:
        config['data']['csv']['file_name'] = override_csv_file_name

    if override_log_file_name != None:
        config['debug']['log']['file_name'] = override_log_file_name

    if config['debug']['log']['enabled']:
        EventLogger.add_logger(FileLogger('FileLogger', log_level_name_to_id(config['debug']['log']['level']),
                                          config['debug']['log']['file_name']))

    try:
        data_logger = DataLogger(config, gui_job)

        if data_logger.ipcon is not None:
            data_logger.run()

            if not gui_start:
                while not interrupted_ref[0]:
                    try:
                        time.sleep(0.25)
                    except:
                        pass

                data_logger.stop()
                sys.exit(0)
        else:
            raise DataLoggerException(DataLoggerException.DL_CRITICAL_ERROR,
                                      "DataLogger did not start logging process! Please check for errors.")

    except Exception as exc:
        EventLogger.critical(str(exc))
        if gui_start:
            return None
        else:
            sys.exit(DataLoggerException.DL_CRITICAL_ERROR)

    return data_logger

if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, '')

    parser = argparse.ArgumentParser(description='Tinkerforge Data Logger')

    class VersionAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            print(data_logger_version)
            sys.exit(0)

    parser.add_argument('-v', '--version', action=VersionAction, nargs=0, help='show version and exit')
    parser.add_argument('config', help='config file location', metavar='CONFIG')
    parser.add_argument('--console-log-level', choices=['none', 'debug', 'info', 'warning', 'error', 'critical'],
                        default='info', help='change console log level (default: info)')
    parser.add_argument('--override-csv-file-name', type=str, default=None,
                        help='override CSV file name in config')
    parser.add_argument('--override-log-file-name', type=str, default=None,
                        help='override log file name in config')

    args = parser.parse_args(sys.argv[1:])

    if args.console_log_level != 'none':
        EventLogger.add_logger(ConsoleLogger('ConsoleLogger', log_level_name_to_id(args.console_log_level)))

    interrupted_ref = [False]

    signal.signal(signal.SIGINT, functools.partial(signal_handler, interrupted_ref))
    signal.signal(signal.SIGTERM, functools.partial(signal_handler, interrupted_ref))

    main(args.config, None, None, args.override_csv_file_name, args.override_log_file_name, interrupted_ref)

