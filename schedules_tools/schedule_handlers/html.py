from schedules_tools.schedule_handlers import ScheduleHandlerBase
import logging
from lxml.html import etree

logger = logging.getLogger(__name__)


date_format = '%Y-%m-%d (%a)'
css = """
table {
    border-collapse: collapse;
}

table th, table td {
    border: 2px solid black;
    padding: 3px;
}

table th {
    background-color: #a5c2ff;
}
table td {
    background-color: #f3ebae;
}
table td.duration {
    text-align: right;
}

table td div.note {
    font-size: 80%;
}
"""


class ScheduleHandler_html(ScheduleHandlerBase):
    provide_export = True
    indent_level_px = 14

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
        e_td.text = str(task.dAcStart.strftime(date_format))

        e_td = etree.SubElement(e_tr, 'td')
        e_td.text = str(task.dAcFinish.strftime(date_format))

        duration = task.dAcFinish - task.dAcStart
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

        title = self.schedule.name
        e_title = etree.SubElement(e_head, 'title')
        e_title.text = title

        e_style = etree.SubElement(e_head, 'style', type='text/css')
        e_style.text = css

        e_body = etree.SubElement(e_html, 'body')

        e_h1 = etree.SubElement(e_body, 'h1')
        e_h1.text = title

        e_table = etree.SubElement(e_body, 'table', align='center')
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
