from schedules_tools.schedule_handlers import ScheduleHandlerBase
import logging
from lxml.html import etree

log = logging.getLogger(__name__)


css = """
a[href=""] {display:none}

table.schedule {
    border-collapse: collapse;
}

table.schedule th, table.schedule td {
    border: 2px solid black;
    padding: 3px 5px;
}

table.schedule th {
    background-color: #a5c2ff;
}
table.schedule td {
    background-color: #f3ebae;
}
table.schedule td.date {
    font-size: 90%;
    white-space: nowrap;
    text-align: right;
}
table.schedule td.duration {
    text-align: right;
}

table.schedule td div.note {
    font-size: 80%;
}
"""


class ScheduleHandler_html(ScheduleHandlerBase):
    provide_export = True

    handle_deps_satisfied = True

    default_export_ext = 'html'

    indent_level_px = 14

    def __init__(self, *args, **kwargs):
        super(ScheduleHandler_html, self).__init__(*args, **kwargs)
        if not self.options.get('date_format', False):
            self.options['date_format'] = '%a %Y-%m-%d'

    @classmethod
    def is_valid_source(cls, handle=None):
        return False

    def _export_task(self, e_table, task, hiearchy_parent='',
                     hiearchy_index=''):
        e_tr = etree.SubElement(e_table, 'tr')
        e_td = etree.SubElement(e_tr, 'td')
        curr_hiearchy_index = str(hiearchy_parent)
        if hiearchy_index:
            curr_hiearchy_index += '.' + str(hiearchy_index)
        e_td.text = curr_hiearchy_index

        padding = (task.level - 1) * self.indent_level_px
        e_td = etree.SubElement(e_tr, 'td',
                                style='padding-left: {}px'.format(padding))
        e_td.text = task.name

        if task.note:
            e_note = etree.SubElement(e_td, 'div')
            e_note.attrib['class'] = 'note'
            e_note.text = task.note

        if task.link:
            e_div = etree.SubElement(e_td, 'div')
            e_link = etree.SubElement(e_div, 'a')
            e_link.attrib['href'] = task.link
            e_link.text = task.link

        e_td = etree.SubElement(e_tr, 'td')
        e_td.attrib['class'] = 'date'
        e_td.text = str(task.dStart.strftime(self.options['date_format']))

        e_td = etree.SubElement(e_tr, 'td')
        e_td.attrib['class'] = 'date'
        e_td.text = str(task.dFinish.strftime(self.options['date_format']))

        duration = task.dFinish - task.dStart
        e_td = etree.SubElement(e_tr, 'td')
        e_td.attrib['class'] = 'duration'
        e_td.text = str(duration.days)

        for index, task in enumerate(task.tasks):
            self._export_task(e_table, task, curr_hiearchy_index, index + 1)

    # Schedule
    def export_schedule(self, out_file=None):
        e_html = etree.Element('html')
        e_head = etree.SubElement(e_html, 'head')

        e_encoding = etree.SubElement(e_head, 'meta', charset="utf-8")

        if self.options.get('html_title', False):
            title = self.options['html_title']
        else:
            title = self.schedule.name
                    
        e_title = etree.SubElement(e_head, 'title')
        e_title.text = title

        e_style = etree.SubElement(e_head, 'style', type='text/css')
        e_style.text = css

        e_body = etree.SubElement(e_html, 'body')

        e_h1 = etree.SubElement(e_body, 'h1')
        e_h1.text = title
        
        if self.options.get('html_table_header', False):
            e_body.append(etree.fromstring(self.options['html_table_header']))

        e_table = etree.SubElement(e_body, 'table', attrib={'align': 'center',
                                                            'class': 'schedule'})
        e_tr_head = etree.SubElement(e_table, 'tr')
        head_columns = ['HierarchIndex', 'Name', 'Start', 'End', 'Duration']
        for column in head_columns:
            e_th_head = etree.SubElement(e_tr_head, 'th')
            e_th_head.text = column

        for index, task in enumerate(self.schedule.tasks):
            self._export_task(e_table, task, index + 1)

        etree_return = etree.ElementTree(e_html)
        if out_file:
            etree_return.write(out_file, pretty_print=True, encoding="utf-8",
                               xml_declaration=False)
        
        return str(etree_return)
