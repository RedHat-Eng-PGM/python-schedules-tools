from . import ScheduleHandlerBase
import datetime
import logging
import fileinput
import os


logger = logging.getLogger('pp.core')

tjp_template = """macro major         [%(major)s]
macro minor         [%(minor)s]
macro maint         [%(maint)s]
macro content       [%(tj_id)s]
macro content_title [%(tj_name)s]
macro start_date    [%(start_date)s]
macro end_date      [%(end_date)s]

macro state         [$State: Exp $]

project ${content}${major}${minor}${maint} "${content_title}" "${major}.${minor}" ${start_date} - ${end_date} {

  # include the Red Hat default values for a program plan
  include "defaults.tji"

}

# include the Red Hat default vacation timing
include "vacations.tji"

# include the Red Hat default resources
include "resources.tji"


include "%(ps_export_file)s"

include "reports.tji"
"""

date_format = '%Y-%m-%d'


class ScheduleHandler_tjp(ScheduleHandlerBase):
    provide_export = True

    @staticmethod
    def is_valid_source(handle):
        # We don't provide any import method
        return False

    # Schedule
    # $(COMMON_DIR)/schedule_convert.py --tj-id $(CONTENT) ${MAJOR_STR} ${MINOR_STR} ${MAINT_STR} $(MSP_SRC) tjp $(MASTER)
    def export_schedule(self, out_file, ps_export_file):
        fp = open(out_file, 'wb')
        fp.write(tjp_template % {
            'major': self.schedule._version['major'],
            'minor': self.schedule._version['minor'],
            'maint': self.schedule._version['maint'],
            'tj_id': self.schedule.tj_id,
            'tj_name': self.schedule.name,
            'start_date': self.schedule.dStart.strftime(date_format),
            'end_date': self.schedule.dFinish.strftime(date_format),
            'current_datetime': datetime.datetime.now().strftime(
                '%Y/%m/%d %H:%M:%S'),
            'ps_export_file': ps_export_file
        })

    # Schedule
    def update_tjp(self, filename):
        # update project frame
        for line in fileinput.input(filename, inplace=True):
            if line.startswith('macro start_date'):
                line = 'macro start_date    [%s]\n' % (
                    self.schedule.dStart.strftime(date_format))

            if line.startswith('macro end_date'):
                line = 'macro end_date      [%s]\n' % (
                    self.schedule.dFinish.strftime(date_format))
