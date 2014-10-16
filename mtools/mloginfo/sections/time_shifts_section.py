from base_section import BaseSection
from mtools.util.print_table import print_table
from mtools.util import OrderedDict
from datetime import date
from mtools.util.logevent import LogEvent
import re, sys, traceback


class TimeShiftSection(BaseSection):
    """ This section determines if there were time changes in the log file and prints out
        the times and information about them.
    """
    
    name = "timeshifts"

    def __init__(self, mloginfo):
        BaseSection.__init__(self, mloginfo)

        # add --restarts flag to argparser
        self.mloginfo.argparser_sectiongroup.add_argument('--timeshifts',
                                                          action='store_true',
                                                          help='outputs about timeshifts, defaults to just the first')
        self.mloginfo.argparser_sectiongroup.add_argument('--fudge',
                                                          default=500,
                                                          help='timeshift fudge factor, defaults to 500 millis')


    @property
    def active(self):
        """ return boolean if this section is active. """
        return self.mloginfo.args['timeshifts']

    def run(self):
        """ run this section and print out information. """

        titles = ['line#', 'start', 'end', 'duration', 'length', 'first']
        table_rows = []
        try:
            fudge = int(self.mloginfo.args['fudge'])
        except ValueError:
            fudge = 500

        for r in self.mloginfo.logfile.time_shifts(fudge):
            stats = OrderedDict()
            stats['line#'] = r.start_line
            stats['start'] = TimeShift.time_str(r.start_time_line)
            stats['end'] = TimeShift.time_str(r.end_time_line)
            stats['duration'] = r.duration_str
            stats['length'] = len(r.lines)
            stats['first'] = "\'" + r.lines[0][-1] + "\'"
            table_rows.append(stats)

        print_table(table_rows, titles, uppercase_headers=False)

        if not(self.mloginfo.logfile.time_shifts(fudge)):
            print "  no time shifts found"


class TimeShift(object):
    """ wrapper class for log files, either as open file streams of from stdin. """
    YEAR = str(date.today().year)
    LAST = None
    OPTIONS = {'Jan': '01',
               'Feb': '02',
               'Mar': '03',
               'Apr': '04',
               'May': '05',
               'Jun': '06',
               'Jul': '07',
               'Aug': '08',
               'Sep': '09',
               'Oct': '10',
               'Nov': '11',
               'Dec': '12'}
    MATCH = re.compile('^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) $').search
    VERSION_22 = "<= 2.2"
    VERSION_24 = "2.4"
    VERSION_26 = "2.6"
    VERSION_28 = ">= 2.8"
    VERSION_UNKNOWN = "unknown"
    TIME_FRAMES = [
        ('yr',        60*60*24*365),
        ('mth',       60*60*24*30),
        ('day',       60*60*24),
        ('hr',        60*60),
        ('min',       60),
        ('sec',       1)
    ]

    def __init__(self):
        """ provide logfile as open file stream or stdin. """
        self.lines = []
        self._start = None
        self._end = None
        self._start_time_line = None
        self._end_time_line = None
        self._start_line = None
        self._end_line = None
        self._duration = None

    def add(self, time, line, no):
        """ Add the line to the list """
        if time is None:
            time = TimeShift.parse_time(line)
        line = line.strip()

        if not self._start or time < self._start:
            self._start = time
            self._start_time_line = line
        if not self._end or time >= self._end:
            self._end = time
            self._end_time_line= line

        self._start_line = no
        self.lines.append([time, line])

    def is_timeshift(self, time, fudge):
        """ add if necessary, if True returned then we added the line. """
        if self._start is None and self._end is None:
            return False
        if self._start == self._end and time > self._end:
            return False

        if len(self.lines) <= 1:
            fudge = 0

        if time < (self._end + fudge ):
            return True

        return False

    def clear(self):
        """ clear the list """
        self._start = None
        self._end = None
        self._start_time_line = None
        self._end_time_line = None
        del self.lines[:]

    def size(self):
        """ get the size of the list """
        return len(self.lines)

    @property
    def start(self):
        """ get the start time """
        return self._start

    @property
    def end(self):
        """ get the end time """
        return self._end

    @property
    def duration(self):
        if self._duration is None:
            s = LogEvent(self.start_time_line)
            e = LogEvent(self.end_time_line)
            self._duration = e.datetime - s.datetime
        return self._duration

    @property
    def duration_str(self):
        return TimeShift.duration_in_words(self.duration)

    @property
    def start_line(self):
        """ the first line in the time shifts """
        return self._start_line

    @property
    def start_time_line(self):
        """ the earliest time in the time shifts """
        return self._start_time_line

    @property
    def end_time_line(self):
        return self._end_time_line

    def lines(self):
        return self.lines

    def empty(self):
        return self.size() <= 1

    @staticmethod
    def matches(line):
        """ Check if line looks like a date """
        return len(line) >= 4 and line[:3] == '201' or line[:3] in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    @staticmethod
    def time_str(line):
        """ Fast but possibly inaccurate time parser """
        version = TimeShift.time_format(line)
        if version == TimeShift.VERSION_22:
            return line[:19]
        if version == TimeShift.VERSION_24:
            return line[:22]
        if version == TimeShift.VERSION_26:
            return line[:27]
        if version == TimeShift.VERSION_28:
            return line[:38]

        return 'unknown'

    @staticmethod
    def reset_on_file():
        """ Reset for each new file  """
        TimeShift.YEAR = str(date.today().year)
        TimeShift.LAST = None

    @staticmethod
    def time_format_28(line):
        """ get time  format
        :param line:
        """
        return line[:3] == '201' and line[23] == '+' and line[40] == '['

    @staticmethod
    def time_format_26(line):
        """ get time  format
        :param line:
        """
        return line[:3] == '201' and line[23] == '+' and line[40] != '['

    @staticmethod
    def time_format_24(line):
        """ get time  format
        :param line:
        """
        return (line[24] == '[' or line[23] == ' ') and TimeShift.matches(line)

    @staticmethod
    def time_format_22(line):
        """ get time  format
        :param line:
        """
        return (line[20] == '[' or line[19] == ' ') and TimeShift.matches(line)

    @staticmethod
    def time_format(line):
        """ get time  format
        :param line:
        """

        if len(line) >= 41:
            if TimeShift.time_format_28(line):
                return TimeShift.VERSION_28
            if TimeShift.time_format_26(line):
                return TimeShift.VERSION_26
            if TimeShift.time_format_24(line):
                return TimeShift.VERSION_24
            if TimeShift.time_format_22(line):
                return TimeShift.VERSION_22
        elif len(line) >= 30:
            if TimeShift.time_format_26(line):
                return TimeShift.VERSION_26
            if TimeShift.time_format_24(line):
                return TimeShift.VERSION_24
            if TimeShift.time_format_22(line):
                return TimeShift.VERSION_22
        elif len(line) >= 25:
            if TimeShift.time_format_24(line):
                return TimeShift.VERSION_24
            if TimeShift.time_format_22(line):
                return TimeShift.VERSION_22
        elif len(line) >= 21:
            if TimeShift.time_format_22(line):
                return TimeShift.VERSION_22
        return TimeShift.VERSION_UNKNOWN

    @staticmethod
    def parse_time(line):
        """ Fast but possibly inaccurate time parser
        :param line:
        """
        try:
            val = None
            version = TimeShift.time_format(line)

            if version == TimeShift.VERSION_24 or version == TimeShift.VERSION_22:
                month = TimeShift.OPTIONS[line[4:7]]
                val = line[9:10] + line[11:13] + line[14:16] + line[17:19]
                if line[8] == ' ':
                    val = '0' + val
                else:
                    val = line[8] + val
                # print val
                val = month + val

                # print val
                if version == TimeShift.VERSION_22:
                    val += '000'
                else:
                    val += line[20:23]

                if month == '01' and TimeShift.LAST == '12':
                    TimeShift.YEAR = str(int(TimeShift.YEAR) + 1)

                TimeShift.LAST = month
                val = TimeShift.YEAR + val
            elif version == TimeShift.VERSION_26 or version == TimeShift.VERSION_28:
                val = line[0:4] + line[5:7] + line[8:10] + line[11:13] + line[14:16] + line[17:19] + line[20:23]

            if val is not None:
                return int(val)
            return val
        except ValueError:
            traceback.print_exc(file=sys.stdout)
            return None

    @staticmethod
    def duration_in_words(td_object):
        """ convert duration / time delta to words """
        seconds = int(td_object.total_seconds())
        strings = []
        for period_name, period_seconds in TimeShift.TIME_FRAMES:
            if seconds > period_seconds:
                period_value , seconds = divmod(seconds,period_seconds)
                if period_value == 1:
                    strings.append("%s %s" % (period_value, period_name))
                else:
                    strings.append("%s %ss" % (period_value, period_name))
        if len(strings) == 0:
            period_value = td_object.microseconds
            if period_value > 1000:
                period_value /= 1000
                period_name = "ms"
            else:
                period_value = period_value
                period_name = "us"

            strings.append("%s %s" % (period_value, period_name))
        return ", ".join(strings)

