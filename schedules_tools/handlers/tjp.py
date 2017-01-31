from . import ScheduleHandlerBase
import datetime
import logging
import fileinput
import tji
import os


logger = logging.getLogger(__name__)
date_format = '%Y-%m-%d'


class ScheduleHandler_tjp(ScheduleHandlerBase):
    provide_export = True
    tjp_template = """macro major         [%(major)s]
macro minor         [%(minor)s]
macro maint         [%(maint)s]
macro content       [%(tj_id)s]
macro content_title [%(tj_name)s]
macro start_date    [%(start_date)s]
macro end_date      [%(end_date)s]

macro state         [$State: Exp $]

project ${content}${major}${minor}${maint} "${content_title}" "${major}.${minor}" ${start_date} - ${end_date} {
  # Add Process Link capabilities
  extend task {
    reference PTask "Process Link"
  }

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

    @staticmethod
    def is_valid_source(handle):
        # We don't provide any import method
        return False

    # Schedule
    # $(COMMON_DIR)/schedule_convert.py --tj-id $(CONTENT) ${MAJOR_STR} ${MINOR_STR} ${MAINT_STR} $(MSP_SRC) tjp $(MASTER)
    def export_schedule(self, out_file):
        tj_id = self.opt_args['tj_id']
        v_major = self.schedule._version['major']
        v_minor = self.schedule._version['minor']
        v_maint = self.schedule._version['maint']

        version_numbers = [tj_id, v_major, v_minor, v_maint]
        if None in version_numbers:
            logger.error('TJP format requires all attributes set: '
                         'tj_id, major, minor, maint')
            return

        # export as TJI first
        logger.info('Producing tji file to include in tjp')
        handle_tji_inst = tji.ScheduleHandler_tji(self.schedule)

        out_tji_parts = version_numbers + ['msp']
        out_tji_file = '-'.join(out_tji_parts) + '.tji'
        handle_tji_inst.schedule.override_version(
            tj_id, v_major, v_minor, v_maint)
        handle_tji_inst.export_schedule(out_tji_file)

        # export TJP with included TJI
        if os.path.exists(out_file):  # create if not exists
            logger.info('tjp already exists - using existing one')
            self.update_tjp(out_file)
            return

        logger.info('tjp file doesn\'t exist - creating one')
        ps_export_file = out_tji_file

        fp = open(out_file, 'wb')

        day = datetime.timedelta(days=1)
        dStart = self.schedule.dStart - day
        dFinish = self.schedule.dFinish + day

        fp.write(self.tjp_template % {
            'major': v_major,
            'minor': v_minor,
            'maint': v_maint,
            'tj_id': self.schedule.tj_id,
            'tj_name': self.schedule.name,
            'start_date': dStart.strftime(date_format),
            'end_date': dFinish.strftime(date_format),
            'current_datetime': datetime.datetime.now().strftime(
                '%Y/%m/%d %H:%M:%S'),
            'ps_export_file': ps_export_file
        })

    # Schedule
    def update_tjp(self, filename):
        # update project frame

        day = datetime.timedelta(days=1)
        dStart = self.schedule.dStart - day
        dFinish = self.schedule.dFinish + day

        for line in fileinput.input(filename, inplace=True):
            if line.startswith('macro start_date'):
                line = 'macro start_date    [%s]\n' % (
                    dStart.strftime(date_format))

            if line.startswith('macro end_date'):
                line = 'macro end_date      [%s]\n' % (
                    dFinish.strftime(date_format))
