#    Copyright (C) 2018 Huawei/Futurewei Technologies
#
#    This Software belongs to the Huawei/Futurewei Technologies. Permission is hereby granted, to the person working on Huawei/Futurewei Technologies projects, including without limitation the rights to use, copy, modify, merge the Software on Huawei/Futurewei Technologies projects.
#
#    Person cannot use, merge, modify, copy this Software on any project which is not owned by Huawei/Futurewei Technologies.
#
#    The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
LOG_FileHandler is to write all logs into LOG_FILENAME
"""
import time
import logging
import sys

# logging.basicConfig(level=logging.DEBUG)
TIME_FORMAT = "%Y_%m_%d_%X_%w_%Z"  # year_month_day_time_weekdayinnumber_timezone
LOG_FILENAME = "logs/" + ("dbg_" if __debug__ else "log_") + time.strftime(TIME_FORMAT) + ".log"


def get_logger(name, debug_level, to_file=True, to_stdout=True, filename=LOG_FILENAME):
    # determine the logging level
    try:
        lev = getattr(logging, debug_level.decode())
    except AttributeError as err:
        if debug_level == b'WARN':
            lev = logging.WARNING
        else:
            raise err
    # set debug level for logger
    logger = logging.getLogger(name)
    logger.handlers = []  # remove default loggers
    logger.setLevel(lev)
    # set log format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # setup log file
    if to_file:
        log_file_handler = logging.FileHandler(filename=filename, mode='a', encoding=None, delay=0)
        log_file_handler.setLevel(level=lev)
        log_file_handler.setFormatter(formatter)
        # add file logger to logger
        logger.addHandler(log_file_handler)
    # setup stdout
    if to_stdout:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(level=lev)
        stdout_handler.setFormatter(formatter)
        # add stdout logger to logger
        logger.addHandler(stdout_handler)
    return logger