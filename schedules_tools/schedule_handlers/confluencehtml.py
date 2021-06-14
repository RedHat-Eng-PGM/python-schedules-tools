import logging

from lxml import etree
from schedules_tools.schedule_handlers import ScheduleHandlerBase


log = logging.getLogger(__name__)


class ScheduleHandler_confluencehtml(ScheduleHandlerBase):
    provide_export = True

    handle_deps_satisfied = True

    default_export_ext = 'html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.options.get('date_format', False):
            self.options['date_format'] = '%a %Y-%m-%d'

    @classmethod
    def is_valid_source(cls, handle=None):
        return False

    def _export_task(self, e_parent, task, top=True):

        if top:  # top level - make p
            e_p = etree.SubElement(e_parent, 'p')
            e_strong = etree.SubElement(e_p, 'strong')
            e_strong.text = task.name
        else:
            e_li = etree.SubElement(e_parent, 'li')
            e_li.text = f'{task.name}'
            e_li.attrib['role'] = 'checkbox'

            if hasattr(task, 'user'):
                e_user = etree.SubElement(e_li, 'em')
                e_user.text = f' [{task.user}]'

        if len(task.tasks):
            e_ul = etree.SubElement(e_parent, 'ul')
            e_ul.attrib['class'] = 'inline-task-list'

            for task in task.tasks:
                self._export_task(e_ul, task, top=False)

        if top:
            etree.SubElement(e_parent, 'br')

    # Schedule
    def export_schedule(self, out_file=None):
        e_html = etree.Element('html')
        e_head = etree.SubElement(e_html, 'head')

        etree.SubElement(e_head, 'meta', charset="utf-8")

        if self.options.get('html_title', False):
            title = self.options['html_title']
        else:
            title = self.schedule.name

        title_date_fmt = '%b %-d'
        start_date = self.schedule.dStart.strftime(title_date_fmt)
        finish_date = self.schedule.dFinish.strftime(title_date_fmt)
        title_text = f'{title} ({start_date} - {finish_date})'

        e_title = etree.SubElement(e_head, 'title')
        e_title.text = title_text

        e_body = etree.SubElement(e_html, 'body')

        e_h = etree.SubElement(e_body, 'h1')
        e_h.text = title_text

        etree.SubElement(e_body, 'br')

        for task in self.schedule.tasks:
            self._export_task(e_body, task)

        etree_return = etree.ElementTree(e_html)
        if out_file:
            etree_return.write(out_file, pretty_print=True, encoding="utf-8",
                               xml_declaration=False)

        return str(etree_return)
