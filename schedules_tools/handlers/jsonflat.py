from schedules_tools.handlers import jsonstruct


class ScheduleHandler_jsonflat(jsonstruct.ScheduleHandler_json):
    provide_export = True
    
    def export_schedule(self):
        return super(ScheduleHandler_jsonflat, self).export_schedule(flat=True)
