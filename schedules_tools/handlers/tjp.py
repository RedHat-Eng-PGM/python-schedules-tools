import datetime
import logging
import fileinput
import os

import tji
from schedules_tools.handlers import ScheduleHandlerBase


logger = logging.getLogger(__name__)
date_format = '%Y-%m-%d'


class ScheduleHandler_tjp(ScheduleHandlerBase):
    """Handles TJP schedules

    opt_args:
        tj_id
        use_tji_file: At first export schedule into TJI file and include it into TJP
        force: Force TJP overwrite
    """
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

include "reports.tji"

%(tjp_content)s
"""

    @staticmethod
    def is_valid_source(handle):
        # We don't provide any import method
        return False

    # Schedule
    # $(COMMON_DIR)/schedule_convert.py --tj-id $(CONTENT) ${MAJOR_STR} ${MINOR_STR} ${MAINT_STR} $(MSP_SRC) tjp $(MASTER)
    def export_schedule(self):
        tj_id = self.opt_args['tj_id']
        use_tji_file = self.opt_args.get('use_tji_file', False)
        force = self.opt_args.get('force', False)

        v_major = self.schedule._version['major']
        v_minor = self.schedule._version['minor']
        v_maint = self.schedule._version['maint']

        version_numbers = [tj_id, v_major, v_minor, v_maint]
        if None in version_numbers:
            logger.error('TJP format requires all attributes set: '
                         'tj_id, major, minor, maint')
            return

        # make sure schedule can fit into project time frame
        day = datetime.timedelta(days=1)
        dStart = self.schedule.dStart - day
        dFinish = self.schedule.dFinish + day


        # export as TJI first
        logger.info('Producing tji file to include in tjp')
        handler_tji = tji.ScheduleHandler_tji(schedule=self.schedule)
        handler_tji.schedule.override_version(
            tj_id, v_major, v_minor, v_maint)

        if use_tji_file:
            out_tji_parts = version_numbers + ['export']
            out_tji_file = '-'.join(out_tji_parts) + '.tji'
            handler_tji.export_schedule(out_tji_file)

            tjp_content = 'include "%s"' % out_tji_file
        else:  # direct schedule as string
            tjp_content = handler_tji.export_schedule()

        # Generate tjp content - we need to return it anyway
        out = self.tjp_template % {
                'major': v_major,
                'minor': v_minor,
                'maint': v_maint,
                'tj_id': self.schedule.tj_id,
                'tj_name': self.schedule.project_name,
                'start_date': dStart.strftime(date_format),
                'end_date': dFinish.strftime(date_format),
                'current_datetime': datetime.datetime.now().strftime(
                    '%Y/%m/%d %H:%M:%S'),
                'tjp_content': tjp_content
        }


        # Update TJP if possible, otherwise create new
        if (os.path.exists(self.handle)
            and use_tji_file
            and not force):
                logger.info('Updating existing TJP file')
                self.update_tjp(self.handle)
        elif self.handle:
            logger.info('Creating new TJP file')
            self._write_to_file(out, self.handle)

        return out


    # Schedule
    def update_tjp(self, filename):
        """Udates project frame"""

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
            print line.rstrip()

